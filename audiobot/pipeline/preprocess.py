import os
import tempfile
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple, Optional

import numpy as np
import soundfile as sf


def _load_silero():
    try:
        import torch
        model, utils = torch.hub.load(
            repo_or_dir='snakers4/silero-vad',
            model='silero_vad',
            force_reload=False,
            trust_repo=True,
            onnx=False,
        ), None
        return model
    except Exception:
        return None


def vad_silero(audio: np.ndarray, sr: int, thresh: float = 0.5, window_ms: float = 30.0) -> np.ndarray:
    """Return frame-wise speech probability using Silero VAD if available; else energy-based.

    audio: mono float32 in [-1,1]
    returns: probs per frame (0..1)
    """
    hop = int(sr * (window_ms / 1000.0))
    if audio.ndim > 1:
        audio = np.mean(audio, axis=1)
    # Attempt Silero
    model = _load_silero()
    if model is not None:
        try:
            import torch
            with torch.inference_mode():
                x = torch.from_numpy(audio).float().unsqueeze(0)
                # The Silero VAD expects 8k/16k; resample if needed
                if sr not in (8000, 16000):
                    import librosa
                    y = librosa.resample(audio, orig_sr=sr, target_sr=16000)
                    x = torch.from_numpy(y).float().unsqueeze(0)
                    sr_eff = 16000
                else:
                    sr_eff = sr
                out = model(x, sr_eff)
                prob = out.squeeze().cpu().numpy()
                # Upsample/downsample probability to hop rate
                # Simple approach: frame at hop
                idx = np.arange(0, len(audio), hop)
                probs = np.interp(idx, np.linspace(0, len(audio) - 1, len(prob)), prob)
                return probs
        except Exception:
            pass
    # Fallback: energy-based VAD
    frames = [audio[i:i + hop] for i in range(0, len(audio), hop)]
    energies = np.array([np.mean(f**2) if len(f) else 0.0 for f in frames])
    # Robust threshold via percentile
    thr = max(1e-8, float(np.percentile(energies, 75)) * 0.3)
    probs = np.clip((energies - thr) / (thr + 1e-8), 0, 1)
    return probs


def segments_from_probs(probs: np.ndarray, sr: int, hop: int, min_speech: float = 0.2, pad: float = 0.05, threshold: float = 0.5) -> List[Tuple[int, int]]:
    segs: List[Tuple[int, int]] = []
    in_seg = False
    start = 0
    for i, p in enumerate(probs):
        if p >= threshold and not in_seg:
            in_seg = True
            start = i
        elif p < threshold and in_seg:
            end = i
            # convert to samples with padding
            s = max(0, start * hop - int(pad * sr))
            e = (end * hop) + int(pad * sr)
            if (e - s) / sr >= min_speech:
                segs.append((s, e))
            in_seg = False
    if in_seg:
        s = max(0, start * hop - int(pad * sr))
        e = len(probs) * hop + int(pad * sr)
        if (e - s) / sr >= min_speech:
            segs.append((s, e))
    return segs


def concat_segments(audio: np.ndarray, segs: List[Tuple[int, int]], crossfade: int = 0) -> np.ndarray:
    chunks = []
    for s, e in segs:
        chunks.append(audio[s:e])
    if not chunks:
        return np.zeros(1, dtype=np.float32)
    out = np.concatenate(chunks)
    return out.astype(np.float32)


def demucs_vocals(input_wav: Path, outdir: Path) -> Optional[Path]:
    """Run Demucs two-stems (vocals) and return path to extracted vocals file.
    Requires 'demucs' CLI in PATH (provided by our env install).
    """
    outdir = outdir.resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    cmd = [
        'demucs', '--two-stems', 'vocals', '-o', str(outdir), str(input_wav)
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    # Demucs output: outdir/model/input_stem.wav
    # Find produced vocals file
    for p in outdir.rglob(f"{input_wav.stem}/vocals*.wav"):
        return p
    # alternative layout
    for p in outdir.rglob("vocals*.wav"):
        if input_wav.stem in p.name:
            return p
    return None


def spectral_gate_dereverb(y: np.ndarray, sr: int, n_fft: int = 1024, hop: int = 256, reduction_db: float = 12.0) -> np.ndarray:
    """Simple spectral gating dereverb/noise reduction.
    Estimate noise floor from 10th percentile per frequency bin and apply soft mask.
    """
    import librosa
    S = librosa.stft(y, n_fft=n_fft, hop_length=hop, win_length=n_fft)
    mag, phase = np.abs(S), np.angle(S)
    # Noise floor per bin
    noise = np.percentile(mag, 10, axis=1, keepdims=True)
    # Soft mask: 1 where speech dominates
    eps = 1e-8
    snr = (mag + eps) / (noise + eps)
    mask = np.clip((snr - 1.0) / snr, 0.0, 1.0)
    # Apply reduction
    att = 10 ** (-reduction_db / 20.0)
    mag_d = mag * (mask + (1 - mask) * att)
    Y = mag_d * np.exp(1j * phase)
    out = librosa.istft(Y, hop_length=hop, win_length=n_fft)
    return out.astype(np.float32)


@dataclass
class PreprocessResult:
    output: Path
    segments_count: int
    temp: Optional[Path] = None


def preprocess_file(input_path: Path, output_path: Path, tmpdir: Optional[Path] = None) -> PreprocessResult:
    """Pipeline: VAD (Silero) → concat speech → Demucs (vocals) → spectral dereverb → write output.
    """
    input_path = Path(input_path)
    output_path = Path(output_path)
    if tmpdir is None:
        tmpdir = Path(tempfile.mkdtemp(prefix='preproc_'))
    tmpdir.mkdir(parents=True, exist_ok=True)

    # Load
    y, sr = sf.read(str(input_path), always_2d=False)
    if y.ndim > 1:
        y = y.mean(axis=1)
    y = y.astype(np.float32)

    # VAD
    window_ms = 30.0
    hop = int(sr * (window_ms / 1000.0))
    probs = vad_silero(y, sr, window_ms=window_ms)
    segs = segments_from_probs(probs, sr, hop, min_speech=0.2, pad=0.05, threshold=0.5)
    speech = concat_segments(y, segs)
    speech_wav = tmpdir / f"{input_path.stem}_speech.wav"
    sf.write(str(speech_wav), speech, sr)

    # Demucs vocals
    demucs_out_base = tmpdir / "demucs"
    vocals_path = demucs_vocals(speech_wav, demucs_out_base)
    if vocals_path and vocals_path.exists():
        v, _ = sf.read(str(vocals_path), always_2d=False)
        if v.ndim > 1:
            v = v.mean(axis=1)
        v = v.astype(np.float32)
    else:
        v = speech

    # Dereverb
    v_d = spectral_gate_dereverb(v, sr, n_fft=1024, hop=256, reduction_db=12.0)

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(output_path), v_d, sr)
    return PreprocessResult(output=output_path, segments_count=len(segs), temp=tmpdir)

