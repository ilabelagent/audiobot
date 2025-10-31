import shutil
import subprocess
from pathlib import Path
from typing import Dict


def separate_stems(
    input_path: Path,
    output_base: Path,
    model: str = "htdemucs",
    stems: int = 4,
    two_stems_target: str = "vocals",
) -> Dict:
    cmd = ["demucs", "-n", model, "-o", str(output_base)]
    if stems == 2:
        cmd += ["--two-stems", two_stems_target]
    cmd.append(str(input_path))
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=7200)
    except subprocess.TimeoutExpired as e:
        return {"returncode": 124, "log": (e.output or "") + "\n[timeout] demucs exceeded timeout", "stems": produced}
    produced = []
    model_dir = output_base / model
    folder = model_dir / input_path.stem
    if folder.exists():
        for wav in folder.glob("*.wav"):
            target_name = f"{input_path.stem}_{wav.stem}.wav"
            target = output_base / target_name
            try:
                shutil.copy2(wav, target)
                produced.append(target.name)
            except Exception:
                pass
    return {"returncode": proc.returncode, "log": proc.stdout, "stems": produced}
