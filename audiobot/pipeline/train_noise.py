from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
import torch
import torch.nn.functional as F
from torch import optim
import pytorch_lightning as pl  # type: ignore

from .models import DenoiserNet
from .datasets import AudioDataset, AudioDataConfig, make_loader


def _download_gcs_prefix(prefix: str, dst_dir: Path) -> None:
    from google.cloud import storage  # type: ignore

    assert prefix.startswith("gs://"), "prefix must start with gs://"
    _, rest = prefix.split("gs://", 1)
    bucket_name, *key_parts = rest.split("/", 1)
    key_prefix = key_parts[0] if key_parts else ""
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blobs = client.list_blobs(bucket, prefix=key_prefix)
    dst_dir.mkdir(parents=True, exist_ok=True)
    for b in blobs:
        if b.name.endswith("/"):
            continue
        local_path = dst_dir / Path(b.name).name
        local_path.parent.mkdir(parents=True, exist_ok=True)
        b.download_to_filename(str(local_path))


class LitDenoiser(pl.LightningModule):
    def __init__(self, lr: float = 1e-3):
        super().__init__()
        self.model = DenoiserNet()
        self.lr = lr

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.model(x)

    def configure_optimizers(self):
        return optim.Adam(self.parameters(), lr=self.lr)

    @staticmethod
    def hf_weight(n_fft: int, device: torch.device) -> torch.Tensor:
        f = torch.linspace(0, 1, steps=n_fft // 2 + 1, device=device)
        w = f**0.5  # emphasize HF a bit
        return w

    def stft_loss(self, pred: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        # pred/target: [B, T]
        win = 1024
        hop = 256
        pred_spec = torch.stft(pred, n_fft=win, hop_length=hop, return_complex=True)
        tgt_spec = torch.stft(target, n_fft=win, hop_length=hop, return_complex=True)
        w = self.hf_weight(win, pred.device)[None, :, None]
        mag_p = pred_spec.abs()
        mag_t = tgt_spec.abs()
        return F.l1_loss(mag_p * w, mag_t * w)

    def training_step(self, batch, batch_idx: int):
        noisy, clean = batch
        noisy = noisy.float()
        clean = clean.float()
        pred = self(noisy)
        l1 = F.l1_loss(pred, clean)
        spec = self.stft_loss(pred, clean)
        loss = l1 + 0.2 * spec
        self.log_dict({"train_l1": l1, "train_stft": spec, "train_loss": loss}, prog_bar=True)
        return loss


def build_datamodule(
    clean_dir: str,
    noisy_dir: Optional[str],
    batch_size: int,
    num_workers: int,
    sample_rate: int,
    chunk_seconds: float,
) -> Tuple[torch.utils.data.DataLoader, torch.utils.data.DataLoader]:
    cfg = AudioDataConfig(sample_rate=sample_rate, chunk_seconds=chunk_seconds, pair_dirs=(noisy_dir is not None))
    ds = AudioDataset(clean_dir=clean_dir, noisy_dir=noisy_dir, cfg=cfg)
    dl = make_loader(ds, batch_size=batch_size, workers=num_workers, shuffle=True)
    # No separate val for simplicity; use a copy with shuffle=False
    dval = make_loader(ds, batch_size=batch_size, workers=num_workers, shuffle=False)
    return dl, dval


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Train Denoiser (noisy sibilance/click/pop)")
    p.add_argument("--clean-dir", required=True, help="Local path or gs:// prefix of clean WAVs")
    p.add_argument("--noisy-dir", default="", help="Optional noisy WAVs (local or gs://); if empty, synthesize noise")
    p.add_argument("--batch-size", type=int, default=16)
    p.add_argument("--workers", type=int, default=2)
    p.add_argument("--epochs", type=int, default=5)
    p.add_argument("--sample-rate", type=int, default=48000)
    p.add_argument("--chunk-seconds", type=float, default=1.0)
    p.add_argument("--lr", type=float, default=1e-3)
    p.add_argument("--outdir", default="web/outputs/models")
    p.add_argument("--save-onnx", action="store_true")
    args = p.parse_args(argv)

    clean_dir = args.clean_dir
    noisy_dir = args.noisy_dir or None

    # If GCS URIs are provided, download to local temp folder
    work_root = Path(os.environ.get("AUDIOBOT_WORK", "./.work"))
    work_root.mkdir(parents=True, exist_ok=True)

    if clean_dir.startswith("gs://"):
        local_clean = work_root / "clean"
        _download_gcs_prefix(clean_dir, local_clean)
        clean_dir = str(local_clean)
    if noisy_dir and noisy_dir.startswith("gs://"):
        local_noisy = work_root / "noisy"
        _download_gcs_prefix(noisy_dir, local_noisy)
        noisy_dir = str(local_noisy)

    train_loader, val_loader = build_datamodule(
        clean_dir=clean_dir,
        noisy_dir=noisy_dir,
        batch_size=args.batch_size,
        num_workers=args.workers,
        sample_rate=args.sample_rate,
        chunk_seconds=args.chunk_seconds,
    )

    model = LitDenoiser(lr=args.lr)
    ckpt_dir = Path(args.outdir)
    ckpt_dir.mkdir(parents=True, exist_ok=True)
    ckpt_cb = pl.callbacks.ModelCheckpoint(dirpath=str(ckpt_dir), save_top_k=1, filename="denoiser-{epoch}-{step}")
    trainer = pl.Trainer(max_epochs=args.epochs, default_root_dir=str(ckpt_dir), callbacks=[ckpt_cb], accelerator="auto")
    trainer.fit(model, train_loader, val_loader)

    if args.save_onnx:
        try:
            onnx_path = ckpt_dir / "denoiser.onnx"
            dummy = torch.randn(1, int(args.sample_rate * args.chunk_seconds))
            torch.onnx.export(model.model, dummy.unsqueeze(1), str(onnx_path), input_names=["noisy"], output_names=["clean"], opset_version=17)
        except Exception:
            pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

