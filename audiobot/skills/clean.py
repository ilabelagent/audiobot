import subprocess
from pathlib import Path


def build_filter_chain(
    noise_reduce: float = 12.0,
    noise_floor: float = -28.0,
    deess_center: float = 0.25,
    deess_strength: float = 1.2,
    highpass: int = 70,
    lowpass: int = 18000,
    limiter: float = 0.95,
) -> str:
    deess_center = max(0.0, min(1.0, deess_center))
    deess_strength = max(0.0, min(2.0, deess_strength))
    limiter = max(0.0, min(1.0, limiter))
    filters = [
        f"afftdn=nr={noise_reduce}:nf={noise_floor}:om=o",
        f"deesser=f={deess_center}:s={deess_strength}",
    ]
    if highpass and highpass > 0:
        filters.append(f"highpass=f={highpass}")
    if lowpass and lowpass > 0:
        filters.append(f"lowpass=f={lowpass}")
    filters.append(f"alimiter=limit={limiter}")
    return ",".join(filters)


def clean_audio(input_path: Path, output_path: Path, af: str, keep_float: bool = False, timeout: float | None = 600) -> subprocess.CompletedProcess:
    codec = "pcm_f32le" if keep_float else "pcm_s16le"
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-y",
        "-i",
        str(input_path),
        "-af",
        af,
        "-c:a",
        codec,
        str(output_path),
    ]
    try:
        return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        # Return a CompletedProcess-like object with timeout info
        cp = subprocess.CompletedProcess(cmd, returncode=124, stdout=(e.output or "") + "\n[timeout] ffmpeg processing exceeded timeout", stderr=None)
        return cp
