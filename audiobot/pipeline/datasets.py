from __future__ import annotations

import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

import numpy as np
import soundfile as sf  # type: ignore
import librosa  # type: ignore
import torch
from torch.utils.data import Dataset, DataLoader


def _resample(y: np.ndarray, sr: int, target_sr: int) -> Tuple[np.ndarray, int]:
    if sr == target_sr:
        return y, sr
    z = librosa.resample(y, orig_sr=sr, target_sr=target_sr, res_type="kaiser_best")
    return z, target_sr


def _to_mono(y: np.ndarray) -> np.ndarray:
    if y.ndim == 2:
        return y.mean(axis=1)
    return y


def _apply_sibilance(y: np.ndarray, sr: int, min_hz: float = 6000.0, max_hz: float = 10000.0, gain_db: float = 8.0) -> np.ndarray:
    # Simple peaking EQ via FFT tilt focusing on band
    n = len(y)
    Y = np.fft.rfft(y)
    freqs = np.fft.rfftfreq(n, 1.0 / sr)
    w = np.ones_like(freqs)
    band = (freqs >= min_hz) & (freqs <= max_hz)
    w[band] *= 10 ** (gain_db / 20.0)
    Z = Y * w
    z = np.fft.irfft(Z, n=n)
    z = z.astype(np.float32)
    z /= max(1.0, np.max(np.abs(z)) + 1e-12)
    return z


def _apply_clicks_pops(y: np.ndarray, rate: float = 0.5, pop_amp: float = 0.8) -> np.ndarray:
    z = y.copy()
    n = len(z)
    n_clicks = max(1, int(rate * 10))
    for _ in range(n_clicks):
        i = random.randint(0, n - 2)
        kind = random.random()
        if kind < 0.5:
            # short impulse (click)
            z[i] += pop_amp * (1 if random.random() < 0.5 else -1)
        else:
            # small step (pop)
            width = random.randint(2, 16)
            sgn = (1 if random.random() < 0.5 else -1) * pop_amp
            z[i : min(n, i + width)] += sgn
    z = np.clip(z, -1.0, 1.0)
    return z


def _apply_hum(y: np.ndarray, sr: int, hum_hz: float = 60.0, gain: float = 0.02) -> np.ndarray:
    t = np.arange(len(y)) / sr
    hum = np.sin(2 * math.pi * hum_hz * t) + 0.3 * np.sin(2 * math.pi * 2 * hum_hz * t)
    z = y + gain * hum.astype(np.float32)
    z = np.clip(z, -1.0, 1.0)
    return z


def _apply_broadband_noise(y: np.ndarray, snr_db: float = 10.0) -> np.ndarray:
    power = np.mean(y**2) + 1e-8
    noise_power = power / (10 ** (snr_db / 10.0))
    noise = np.random.normal(scale=np.sqrt(noise_power), size=y.shape).astype(np.float32)
    z = y + noise
    z = np.clip(z, -1.0, 1.0)
    return z


def _random_crop(y: np.ndarray, length: int) -> np.ndarray:
    if len(y) <= length:
        if len(y) == length:
            return y
        pad = length - len(y)
        return np.pad(y, (0, pad))
    start = random.randint(0, len(y) - length)
    return y[start : start + length]


@dataclass
class AudioDataConfig:
    sample_rate: int = 48000
    chunk_seconds: float = 1.0
    pair_dirs: bool = False  # if True, expects clean_dir and noisy_dir, else synthesize noise


class AudioDataset(Dataset):
    def __init__(
        self,
        clean_dir: str,
        noisy_dir: Optional[str] = None,
        cfg: AudioDataConfig = AudioDataConfig(),
    ) -> None:
        self.clean_paths: List[Path] = [
            p for p in Path(clean_dir).rglob("*.wav")
        ]
        self.noisy_paths: Optional[List[Path]] = None
        self.cfg = cfg
        if cfg.pair_dirs:
            assert noisy_dir is not None, "noisy_dir required when pair_dirs=True"
            self.noisy_paths = [p for p in Path(noisy_dir).rglob("*.wav")]
            assert len(self.clean_paths) == len(self.noisy_paths), "paired datasets must be same length"
        self.chunk_len = int(cfg.sample_rate * cfg.chunk_seconds)

    def __len__(self) -> int:
        return len(self.clean_paths)

    def _load(self, p: Path) -> np.ndarray:
        y, sr = sf.read(str(p), always_2d=False)
        y = _to_mono(y)
        y, _ = _resample(y, sr, self.cfg.sample_rate)
        y = y.astype(np.float32)
        if np.max(np.abs(y)) > 0:
            y = y / (np.max(np.abs(y)) + 1e-12)
        return y

    def _synthesize(self, clean: np.ndarray) -> np.ndarray:
        z = clean.copy()
        if random.random() < 0.9:
            z = _apply_sibilance(z, self.cfg.sample_rate, gain_db=random.uniform(5.0, 12.0))
        if random.random() < 0.8:
            z = _apply_clicks_pops(z, rate=random.uniform(0.2, 0.8), pop_amp=random.uniform(0.3, 0.9))
        if random.random() < 0.7:
            z = _apply_hum(z, self.cfg.sample_rate, hum_hz=random.choice([50.0, 60.0]), gain=random.uniform(0.005, 0.03))
        if random.random() < 0.9:
            z = _apply_broadband_noise(z, snr_db=random.uniform(0.0, 15.0))
        return z

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        clean = self._load(self.clean_paths[idx])
        if self.noisy_paths is not None:
            noisy = self._load(self.noisy_paths[idx])  # type: ignore[index]
        else:
            noisy = self._synthesize(clean)
        clean = _random_crop(clean, self.chunk_len)
        noisy = _random_crop(noisy, self.chunk_len)
        return torch.from_numpy(noisy), torch.from_numpy(clean)


def make_loader(ds: Dataset, batch_size: int = 16, workers: int = 2, shuffle: bool = True) -> DataLoader:
    return DataLoader(ds, batch_size=batch_size, shuffle=shuffle, num_workers=workers, pin_memory=True)

