from __future__ import annotations

import numpy as np
import pyloudnorm as pyln  # type: ignore


def to_mono(x: np.ndarray) -> np.ndarray:
    if x.ndim == 1:
        return x
    return np.mean(x, axis=1)


def normalize_lufs(x: np.ndarray, sr: int, target_lufs: float = -14.0) -> np.ndarray:
    meter = pyln.Meter(sr)
    loudness = meter.integrated_loudness(x)
    gain_db = target_lufs - loudness
    gain = 10.0 ** (gain_db / 20.0)
    y = x * gain
    peak = np.max(np.abs(y)) + 1e-12
    if peak > 1.0:
        y = y / peak
    return y


def highpass(x: np.ndarray, sr: int, cutoff: float = 60.0) -> np.ndarray:
    # simple first-order high-pass (RC)
    rc = 1.0 / (2 * np.pi * cutoff)
    dt = 1.0 / sr
    alpha = rc / (rc + dt)
    y = np.zeros_like(x)
    prev_y = 0.0
    prev_x = 0.0
    for i in range(x.shape[0]):
        prev_y = alpha * (prev_y + x[i] - prev_x)
        y[i] = prev_y
        prev_x = x[i]
    return y


def soft_clip_dbfs(x: np.ndarray, ceiling_dbfs: float = -1.0) -> np.ndarray:
    ceiling = 10 ** (ceiling_dbfs / 20.0)
    return np.clip(x, -ceiling, ceiling)


def band_suppress_sibilance(x: np.ndarray, sr: int, f_lo: float = 5000.0, f_hi: float = 9000.0, depth_db: float = -3.0) -> np.ndarray:
    # naive static band attenuation using FFT masking
    X = np.fft.rfft(x)
    freqs = np.fft.rfftfreq(x.size, 1.0 / sr)
    mask = np.ones_like(X, dtype=float)
    band = (freqs >= f_lo) & (freqs <= f_hi)
    mask[band] *= 10 ** (depth_db / 20.0)
    Y = X * mask
    y = np.fft.irfft(Y, n=x.size)
    return y.astype(x.dtype, copy=False)

