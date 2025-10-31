from __future__ import annotations

from pathlib import Path
import numpy as np
import soundfile as sf  # type: ignore
import librosa  # type: ignore
import pyloudnorm as pyln  # type: ignore
try:
    import noisereduce as nr  # type: ignore
except Exception:  # pragma: no cover
    nr = None

from .utils import (
    highpass,
    normalize_lufs,
    band_suppress_sibilance,
    soft_clip_dbfs,
)


def _ensure_sr(x: np.ndarray, sr: int, target_sr: int = 48000) -> tuple[np.ndarray, int]:
    if sr == target_sr:
        return x, sr
    y = librosa.resample(x.T, orig_sr=sr, target_sr=target_sr, res_type="kaiser_best").T
    return y, target_sr


def _stereo(fn):
    def wrapper(*args, **kwargs):
        return fn(*args, **kwargs)
    return wrapper


def clean_array(x: np.ndarray, sr: int, target_lufs: float = -14.0, deess: bool = True) -> tuple[np.ndarray, int]:
    # convert to float32 range [-1,1]
    if x.dtype != np.float32 and x.dtype != np.float64:
        peak = np.iinfo(x.dtype).max
        x = x.astype(np.float32) / peak

    if x.ndim == 2:
        # process mid/side lightly to avoid phase issues
        mid = x.mean(axis=1)
        side = x[:, 0] - x[:, 1]
        mid = highpass(mid, sr, 60.0)
        if deess:
            mid = band_suppress_sibilance(mid, sr, 5000.0, 9000.0, -2.5)
        if nr is not None:
            try:
                mid = nr.reduce_noise(y=mid, sr=sr, prop_decrease=0.25)
            except Exception:
                pass
        # reconstruct
        left = (mid + side / 2.0)
        right = (mid - side / 2.0)
        y = np.stack([left, right], axis=1)
    else:
        y = highpass(x, sr, 60.0)
        if deess:
            y = band_suppress_sibilance(y, sr, 5000.0, 9000.0, -2.5)
        if nr is not None:
            try:
                y = nr.reduce_noise(y=y, sr=sr, prop_decrease=0.25)
            except Exception:
                pass

    y, sr = _ensure_sr(y, sr, 48000)
    # Compute LUFS gain using mono reference, apply to all channels to preserve stereo image
    ref = y if y.ndim == 1 else y.mean(axis=1)
    meter = pyln.Meter(sr)
    try:
        loudness = meter.integrated_loudness(ref)
        gain_db = target_lufs - float(loudness)
        gain = 10.0 ** (gain_db / 20.0)
    except Exception:
        gain = 1.0
    y = y * float(gain)
    # If any peak exceeds 1.0, scale back to avoid clipping before soft ceiling
    peak = np.max(np.abs(y)) + 1e-12
    if peak > 1.0:
        y = y / peak
    if y.ndim == 1:
        y = y[:, None]
    y = np.tile(y, (1, 2)) if y.shape[1] == 1 else y
    y = soft_clip_dbfs(y, -1.0)
    return y.astype(np.float32), sr


def clean_audio(input_path: str, output_path: str, target_lufs: float = -14.0, deess: bool = True) -> None:
    x, sr = sf.read(input_path, always_2d=False)
    y, sr = clean_array(x, sr, target_lufs=target_lufs, deess=deess)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    sf.write(output_path, y, sr, subtype="PCM_24")
