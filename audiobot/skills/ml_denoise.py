from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
import soundfile as sf  # type: ignore
import librosa  # type: ignore


def _maybe_download_gcs(uri: str, dst: Path) -> Path:
    if not uri.startswith("gs://"):
        return Path(uri)
    try:
        from google.cloud import storage  # type: ignore
    except Exception:
        raise RuntimeError("google-cloud-storage not installed; cannot download gs:// model")
    bucket_name, *key_parts = uri.replace("gs://", "").split("/", 1)
    key = key_parts[0] if key_parts else ""
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(key)
    dst.parent.mkdir(parents=True, exist_ok=True)
    blob.download_to_filename(str(dst))
    return dst


def _load_torch_model(model_path: Path):
    import torch
    from ..pipeline.models import DenoiserNet

    model = DenoiserNet()
    ckpt = torch.load(str(model_path), map_location="cpu")
    state = ckpt.get("state_dict") if isinstance(ckpt, dict) else None
    if state:
        # strip optional 'model.' prefix from LightningModule
        new_state = {}
        for k, v in state.items():
            if k.startswith("model."):
                new_state[k[len("model."):]] = v
            else:
                new_state[k] = v
        model.load_state_dict(new_state, strict=False)
    elif isinstance(ckpt, dict):
        model.load_state_dict(ckpt, strict=False)
    else:
        raise RuntimeError("Unsupported checkpoint format")
    model.eval()
    return model


def _infer_torch(model, audio: np.ndarray, sample_rate: int, chunk_seconds: float, overlap_seconds: float, device: Optional[str] = None) -> np.ndarray:
    import torch

    device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    model = model.to(device)
    n = len(audio)
    chunk = max(1, int(sample_rate * float(chunk_seconds)))
    overlap = max(0, int(sample_rate * float(overlap_seconds)))
    hop = max(1, chunk - overlap)
    if chunk >= n:
        x = torch.from_numpy(audio).float().unsqueeze(0).to(device)
        with torch.no_grad():
            y = model(x).squeeze(0).cpu().numpy()
        return y
    out = np.zeros(n, dtype=np.float32)
    wsum = np.zeros(n, dtype=np.float32)
    win = np.hanning(chunk).astype(np.float32)
    i = 0
    while i < n:
        seg = audio[i : min(n, i + chunk)]
        if len(seg) < chunk:
            seg = np.pad(seg, (0, chunk - len(seg)))
            w = win.copy()
            w[len(audio) - i :] = 0.0
        else:
            w = win
        x = torch.from_numpy(seg).float().unsqueeze(0).to(device)
        with torch.no_grad():
            y = model(x).squeeze(0).cpu().numpy().astype(np.float32)
        L = min(chunk, n - i)
        out[i : i + L] += y[:L] * w[:L]
        wsum[i : i + L] += w[:L]
        i += hop
    wsum = np.maximum(wsum, 1e-6)
    out = out / wsum
    return out


def ml_denoise(
    input_path: Path,
    output_path: Path,
    model_path: str,
    sample_rate: int = 48000,
    chunk_seconds: float = 1.0,
    overlap_seconds: float = 0.1,
    device: Optional[str] = None,
) -> Dict[str, Any]:
    """Run ML denoiser (PyTorch checkpoint or ONNX) on an input WAV.

    If `model_path` starts with gs://, downloads to .work/models first.
    """
    try:
        mp = model_path
        if model_path.startswith("gs://"):
            mp = str(_maybe_download_gcs(model_path, Path(".work") / "models" / Path(model_path).name))
        p = Path(mp)
        x, sr = sf.read(str(input_path), always_2d=False)
        if x.ndim == 2:
            x = x.mean(axis=1)
        if sr != sample_rate:
            x = librosa.resample(x, sr, sample_rate, res_type="kaiser_best")
            sr = sample_rate
        x = x.astype(np.float32)
        peak = float(np.max(np.abs(x)) + 1e-12)
        if peak > 0:
            x = x / peak

        if p.suffix.lower() in {".pt", ".pth", ".ckpt"}:
            model = _load_torch_model(p)
            y = _infer_torch(model, x, sr, chunk_seconds, overlap_seconds, device=device)
        elif p.suffix.lower() == ".onnx":
            try:
                import onnxruntime as ort  # type: ignore
            except Exception:
                return {"ok": False, "log": "onnxruntime not installed; cannot run ONNX model"}
            sess = ort.InferenceSession(str(p), providers=["CPUExecutionProvider"])  # simple CPU infer
            # frame-based similar to torch path for consistency
            chunk = max(1, int(sr * float(chunk_seconds)))
            overlap = max(0, int(sr * float(overlap_seconds)))
            hop = max(1, chunk - overlap)
            n = len(x)
            if chunk >= n:
                y = sess.run(None, {sess.get_inputs()[0].name: x.astype(np.float32)[None, None, :]})[0].squeeze()
            else:
                out = np.zeros(n, dtype=np.float32)
                wsum = np.zeros(n, dtype=np.float32)
                win = np.hanning(chunk).astype(np.float32)
                i = 0
                while i < n:
                    seg = x[i : min(n, i + chunk)]
                    if len(seg) < chunk:
                        seg = np.pad(seg, (0, chunk - len(seg)))
                        w = win.copy()
                        w[len(x) - i :] = 0.0
                    else:
                        w = win
                    pred = sess.run(None, {sess.get_inputs()[0].name: seg.astype(np.float32)[None, None, :]})[0].squeeze().astype(np.float32)
                    L = min(chunk, n - i)
                    out[i : i + L] += pred[:L] * w[:L]
                    wsum[i : i + L] += w[:L]
                    i += hop
                wsum = np.maximum(wsum, 1e-6)
                y = out / wsum

        else:
            return {"ok": False, "log": f"Unsupported model extension: {p.suffix}"}

        # duplicate mono to stereo for compatibility
        y = np.clip(y, -1.0, 1.0)
        y_st = np.stack([y, y], axis=1)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(output_path), y_st, sr, subtype="PCM_24")
        return {"ok": True, "output": str(output_path)}
    except Exception as e:
        return {"ok": False, "log": str(e)}

