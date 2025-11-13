from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def separate_stems(input_wav: str, out_dir: str) -> bool:
    """
    Try to run Demucs separation if available. Returns True if succeeded.
    Prefers CLI call to avoid tight coupling with internal API.
    """
    if not shutil.which("python"):
        return False
    # Check demucs availability by attempting an import via python -c
    chk = subprocess.run(["python", "-c", "import demucs"], capture_output=True)
    if chk.returncode != 0:
        return False

    Path(out_dir).mkdir(parents=True, exist_ok=True)
    cmd = [
        "python",
        "-m",
        "demucs.separate",
        "-o",
        out_dir,
        input_wav,
    ]
    proc = subprocess.run(cmd)
    return proc.returncode == 0

