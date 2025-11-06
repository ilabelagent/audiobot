from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from .memory import Memory
from .skills import build_filter_chain, clean_audio, separate_stems, analyze_audio, download_video as skill_download_video, extract_audio as skill_extract_audio, transcribe_audio
from .sync.gcs import upload_if_configured
from .sync.ipfs import pin_file


@dataclass
class Skill:
    name: str
    run: Callable[..., Any]
    description: str = ""


@dataclass
class Bot:
    root: Path = field(default_factory=lambda: Path.cwd())
    db_path: Path = field(default_factory=lambda: Path("data") / "audiobot.db")
    memory: Memory = field(init=False)
    skills: Dict[str, Skill] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.memory = Memory(self.db_path)
        self.register_defaults()

    def register(self, name: str, func: Callable[..., Any], description: str = "") -> None:
        self.skills[name] = Skill(name=name, run=func, description=description)

    def register_defaults(self) -> None:
        self.register("clean", self._skill_clean, "Clean audio with FFmpeg filters")
        self.register("separate", self._skill_separate, "Separate stems with Demucs")
        self.register("inspect", self._skill_inspect, "Inspect audio properties")
        self.register("download", self._skill_download, "Download video by URL (yt-dlp)")
        self.register("extract", self._skill_extract, "Extract audio track from media")
        # Seed default presets if missing
        try:
            if not self.memory.get_preset("VERY_NOISY_VOX"):
                self.memory.save_preset(
                    "VERY_NOISY_VOX",
                    {
                        "preset": "very_noisy_vox",
                        "noise_reduce": 12.0,
                        "noise_floor": -28.0,
                        "deess_center": 0.25,
                        "deess_strength": 1.2,
                        "highpass": 80,
                        "lowpass": 18000,
                        "limiter": 0.95,
                        "gate": True,
                        "air_bus": True,
                        "air_mix": 0.2,
                        "declick": True,
                        "declip": True,
                        "post_deess_center": 0.35,
                        "post_deess_strength": 0.0,
                    },
                )
            if not self.memory.get_preset("LOUD_SLAM"):
                self.memory.save_preset(
                    "LOUD_SLAM",
                    {
                        "preset": "very_noisy_vox",
                        "noise_reduce": 10.0,
                        "noise_floor": -30.0,
                        "deess_center": 0.28,
                        "deess_strength": 1.3,
                        "highpass": 90,
                        "lowpass": 18000,
                        "limiter": 0.99,
                        "gate": True,
                        "air_bus": True,
                        "air_mix": 0.22,
                        "declick": True,
                        "declip": True,
                        "post_deess_center": 0.35,
                        "post_deess_strength": 0.6,
                    },
                )
            if not self.memory.get_preset("VERY_LOUD_CRISPY"):
                self.memory.save_preset(
                    "VERY_LOUD_CRISPY",
                    {
                        "preset": "very_loud_crispy",
                        "noise_reduce": 8.0,
                        "noise_floor": -30.0,
                        "deess_center": 0.28,
                        "deess_strength": 1.3,
                        "highpass": 90,
                        "lowpass": 20000,
                        "limiter": 0.99,
                        "gate": True,
                        "air_bus": True,
                        "air_mix": 0.25,
                        "declick": True,
                        "declip": True,
                        "post_deess_center": 0.35,
                        "post_deess_strength": 0.4,
                    },
                )
            if not self.memory.get_preset("MAX_LOUDNESS"):
                self.memory.save_preset(
                    "MAX_LOUDNESS",
                    {
                        "preset": "max_loudness",
                        "noise_reduce": 8.0,
                        "noise_floor": -32.0,
                        "deess_center": 0.30,
                        "deess_strength": 1.4,
                        "highpass": 100,
                        "lowpass": 20000,
                        "limiter": 0.99,
                        "gate": True,
                        "gate_thresh_db": -45.0,
                        "air_bus": True,
                        "air_mix": 0.30,
                        "air_highpass_hz": 10000,
                        "air_shelf_gain_db": 4.0,
                        "air_deess_strength": 1.6,
                        "declick": True,
                        "declip": True,
                        "post_deess_center": 0.35,
                        "post_deess_strength": 0.7,
                    },
                )
        except Exception:
            # Preset seeding is best-effort; ignore DB errors here
            pass
        self.register("transcribe", self._skill_transcribe, "Transcribe audio with Google Speech-to-Text")
        self.register("denoise", self._skill_denoise, "ML denoiser inference (PyTorch/ONNX)")

    # Skill wrappers using memory bookkeeping
    def _skill_clean(
        self,
        input_path: Path,
        output_path: Optional[Path] = None,
        keep_float: bool = False,
        **params: Any,
    ) -> Dict[str, Any]:
        input_path = Path(input_path)
        output_path = Path(output_path) if output_path else input_path.with_name(f"{input_path.stem}_clean.wav")
        af = build_filter_chain(**params)
        proc = clean_audio(input_path, output_path, af, keep_float)
        ok = output_path.exists() and output_path.stat().st_size > 0 and proc.returncode == 0
        job_id = self.memory.record_job("clean", str(input_path), str(output_path), {"keep_float": keep_float, **params}, ok)
        # Quick metrics
        metrics = analyze_audio(output_path) if ok else {}
        if metrics:
            if metrics.get("rms") is not None:
                self.memory.record_metric(job_id, "rms", float(metrics["rms"]))
            if metrics.get("peak") is not None:
                self.memory.record_metric(job_id, "peak", float(metrics["peak"]))
        ipfs = None
        gs_url = None
        if ok:
            try:
                gs_url = upload_if_configured(str(output_path))
            except Exception:
                gs_url = None
            try:
                pin = pin_file(str(output_path))
                if pin:
                    ipfs = {"cid": pin.get("cid", ""), "url": pin.get("gateway_url")}
            except Exception:
                ipfs = None
        return {"ok": ok, "output": str(output_path) if ok else None, "gcs": gs_url, "ipfs": ipfs, "log": proc.stdout}

    def _skill_separate(
        self,
        input_path: Path,
        output_base: Optional[Path] = None,
        model: str = "htdemucs",
        stems: int = 4,
        two_stems_target: str = "vocals",
    ) -> Dict[str, Any]:
        input_path = Path(input_path)
        output_base = Path(output_base) if output_base else input_path.parent
        res = separate_stems(input_path, output_base, model=model, stems=stems, two_stems_target=two_stems_target)
        ok = (res.get("returncode", 1) == 0) and len(res.get("stems", [])) > 0
        self.memory.record_job(
            "separate", str(input_path), str(output_base), {"model": model, "stems": stems, "two_stems_target": two_stems_target}, ok
        )
        uploaded = []
        if ok:
            stems_list = res.get("stems", [])
            for name in stems_list:
                p = output_base / name if not Path(name).is_absolute() else Path(name)
                entry = {"name": name, "gcs": None, "ipfs": None}
                try:
                    entry["gcs"] = upload_if_configured(str(p))
                except Exception:
                    pass
                try:
                    pin = pin_file(str(p))
                    if pin:
                        entry["ipfs"] = {"cid": pin.get("cid", ""), "url": pin.get("gateway_url")}
                except Exception:
                    pass
                uploaded.append(entry)
        return {"ok": ok, "stems": res.get("stems", []), "uploaded": uploaded, "log": res.get("log", "")}

    def _skill_denoise(
        self,
        input_path: Path,
        output_path: Optional[Path] = None,
        model_path: str = "",
        sample_rate: int = 48000,
        chunk_seconds: float = 1.0,
        overlap_seconds: float = 0.1,
        device: str | None = None,
    ) -> Dict[str, Any]:
        from .skills import ml_denoise

        input_path = Path(input_path)
        output_path = Path(output_path) if output_path else input_path.with_name(f"{input_path.stem}_ml.wav")
        res = ml_denoise(input_path, output_path, model_path=model_path, sample_rate=sample_rate, chunk_seconds=chunk_seconds, overlap_seconds=overlap_seconds, device=device)
        ok = bool(res.get("ok")) and output_path.exists()
        job_id = self.memory.record_job(
            "denoise",
            str(input_path),
            str(output_path),
            {"model_path": model_path, "sample_rate": sample_rate, "chunk_seconds": chunk_seconds, "overlap_seconds": overlap_seconds},
            ok,
        )
        gs_url = None
        ipfs = None
        if ok:
            try:
                gs_url = upload_if_configured(str(output_path))
            except Exception:
                gs_url = None
            try:
                pin = pin_file(str(output_path))
                if pin:
                    ipfs = {"cid": pin.get("cid", ""), "url": pin.get("gateway_url")}
            except Exception:
                ipfs = None
        return {"ok": ok, "output": str(output_path) if ok else None, "gcs": gs_url, "ipfs": ipfs, "log": res.get("log", "")}

    def _skill_inspect(self, input_path: Path) -> Dict[str, Any]:
        input_path = Path(input_path)
        res = analyze_audio(input_path)
        self.memory.record_job("inspect", str(input_path), "", {}, True)
        return res

    def _skill_download(self, url: str, out_dir: Optional[Path] = None) -> Dict[str, Any]:
        out = Path(out_dir or Path("web") / "uploads")
        res = skill_download_video(url, out)
        ok = bool(res.get("ok"))
        path = res.get("path") or ""
        self.memory.record_job("download", url, path, {}, ok)
        return {"ok": ok, "path": path, "log": res.get("log", "")}

    def _skill_extract(self, input_path: Path, output_path: Optional[Path] = None, samplerate: int = 48000, stereo: bool = True) -> Dict[str, Any]:
        input_path = Path(input_path)
        output_path = Path(output_path) if output_path else input_path.with_suffix(".wav")
        proc = skill_extract_audio(input_path, output_path, samplerate=samplerate, stereo=stereo)
        ok = output_path.exists() and output_path.stat().st_size > 0 and proc.returncode == 0
        self.memory.record_job("extract", str(input_path), str(output_path), {"samplerate": samplerate, "stereo": stereo}, ok)
        return {"ok": ok, "output": str(output_path) if ok else None, "log": proc.stdout}

    def _skill_transcribe(self, input_path: Path) -> Dict[str, Any]:
        input_path = Path(input_path)
        res = transcribe_audio(input_path)
        ok = bool(res.get("ok"))
        self.memory.record_job("transcribe", str(input_path), "", {}, ok)
        return res

    # Simple trainable preferences: averages per usage context
    def learn_preference(self, context: str, params: Dict[str, Any]) -> None:
        key = f"pref:{context}"
        data = self.memory.kv_get(key) or {"count": 0}
        count = int(data.get("count", 0))
        # Maintain running averages for numeric params
        for k, v in params.items():
            if isinstance(v, (int, float)):
                prev = float(data.get(k, v))
                new = (prev * count + float(v)) / (count + 1)
                data[k] = new
        data["count"] = count + 1
        self.memory.kv_set(key, data)

    def recommend(self, context: str, default: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        key = f"pref:{context}"
        base = default.copy() if default else {}
        learned = self.memory.kv_get(key) or {}
        for k, v in learned.items():
            if k == "count":
                continue
            base[k] = v
        return base
