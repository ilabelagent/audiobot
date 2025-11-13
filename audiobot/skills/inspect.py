import subprocess
from pathlib import Path
from typing import Dict


def analyze_audio(path: Path) -> Dict:
    cmd = [
        "ffprobe",
        "-hide_banner",
        "-v",
        "error",
        "-show_entries",
        "stream=index,codec_name,codec_type,channels,sample_rate,bit_rate",
        "-show_format",
        "-of",
        "json",
        str(path),
    ]
    p1 = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    rms = None
    peak = None
    try:
        p2 = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-i",
                str(path),
                "-af",
                "astats=metadata=1:reset=1,ametadata=print:key=lavfi.astats.Overall.RMS_level:mode=print",
                "-f",
                "null",
                "-",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        for line in p2.stdout.splitlines():
            if "RMS_level" in line:
                parts = line.split("=")
                if len(parts) == 2:
                    rms = float(parts[1])
                    break
        p3 = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-i",
                str(path),
                "-af",
                "astats=metadata=1:reset=1,ametadata=print:key=lavfi.astats.Overall.Peak_level:mode=print",
                "-f",
                "null",
                "-",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        for line in p3.stdout.splitlines():
            if "Peak_level" in line:
                parts = line.split("=")
                if len(parts) == 2:
                    peak = float(parts[1])
                    break
    except Exception:
        pass
    return {"probe": p1.stdout, "rms": rms, "peak": peak}

