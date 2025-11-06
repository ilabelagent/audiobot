import argparse
import sys
from pathlib import Path

from .processing.clean import clean_audio
from .stems.demucs import separate_stems
from .core import Bot

# Optional ML training imports are lazy; we import inside handlers to avoid hard deps.


def cmd_clean(args: argparse.Namespace) -> int:
    inp = Path(args.input)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    # ML denoiser path takes precedence when specified
    if getattr(args, "ml_model", ""):
        bot = Bot()
        res = bot.skills["denoise"].run(
            inp,
            out,
            model_path=args.ml_model,
            sample_rate=getattr(args, "ml_sample_rate", 48000),
            chunk_seconds=getattr(args, "ml_chunk_seconds", 1.0),
            overlap_seconds=getattr(args, "ml_overlap", 0.1),
            device=(getattr(args, "ml_device", "") or None),
        )
        if not res.get("ok"):
            print("ML denoise failed:", res.get("log", ""))
            return 2
        print(f"Denoised (ML) -> {out}")
        return 0
    if args.preset:
        # Route to FFmpeg-based skill via Bot to honor presets
        bot = Bot()
        params = {
            "preset": args.preset,
            "air_bus": args.air_bus,
            "air_mix": args.air_mix,
            "gate": (not args.no_gate),
            "gate_thresh_db": args.gate_thresh_db,
            # conservative base values; user can adjust later if needed
            "noise_reduce": 12.0,
            "noise_floor": -28.0,
            "deess_center": 0.25,
            "deess_strength": 1.2,
            "highpass": 70,
            "lowpass": 18000,
            "limiter": 0.95,
            "declick": (not args.no_declick),
            "declip": (not args.no_declip),
            "air_highpass_hz": args.air_highpass,
            "air_shelf_gain_db": args.air_shelf_db,
            "air_deess_strength": args.air_deess_strength,
            "post_deess_center": args.post_deess_center,
            "post_deess_strength": args.post_deess_strength,
        }
        # Support DB presets via --preset db:NAME
        if str(args.preset).lower().startswith("db:"):
            from .memory import Memory
            name = str(args.preset).split(":",1)[1]
            dbp = Memory().get_preset(name)
            if isinstance(dbp, dict) and dbp:
                params.update(dbp)
        res = bot.skills["clean"].run(inp, out, args.keep_float, **params)
        if not res.get("ok"):
            print("FFmpeg preset clean failed:", res.get("log", ""))
            return 2
        print(f"Cleaned (preset) -> {out}")
        return 0
    # Default Python DSP cleaner
    clean_audio(str(inp), str(out), target_lufs=args.lufs, deess=not args.no_deess)
    print(f"Cleaned -> {out}")
    return 0


def cmd_batch(args: argparse.Namespace) -> int:
    in_dir = Path(args.input)
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for p in in_dir.rglob("*.wav"):
        dest = out_dir / p.name
        if getattr(args, "ml_model", ""):
            bot = Bot()
            res = bot.skills["denoise"].run(
                p,
                dest,
                model_path=args.ml_model,
                sample_rate=getattr(args, "ml_sample_rate", 48000),
                chunk_seconds=getattr(args, "ml_chunk_seconds", 1.0),
                overlap_seconds=getattr(args, "ml_overlap", 0.1),
                device=(getattr(args, "ml_device", "") or None),
            )
            if not res.get("ok"):
                print("ML denoise failed for", p, ":", res.get("log", ""))
                continue
        elif getattr(args, "preset", ""):
            bot = Bot()
            params = {
                "preset": args.preset,
                "air_bus": args.air_bus,
                "air_mix": args.air_mix,
                "gate": (not args.no_gate),
                "gate_thresh_db": args.gate_thresh_db,
                "noise_reduce": 12.0,
                "noise_floor": -28.0,
                "deess_center": 0.25,
                "deess_strength": 1.2,
                "highpass": 70,
                "lowpass": 18000,
                "limiter": 0.95,
                "declick": (not args.no_declick),
                "declip": (not args.no_declip),
                "air_highpass_hz": args.air_highpass,
                "air_shelf_gain_db": args.air_shelf_db,
                "air_deess_strength": args.air_deess_strength,
                "post_deess_center": args.post_deess_center,
                "post_deess_strength": args.post_deess_strength,
            }
            if str(args.preset).lower().startswith("db:"):
                from .memory import Memory
                name = str(args.preset).split(":",1)[1]
                dbp = Memory().get_preset(name)
                if isinstance(dbp, dict) and dbp:
                    params.update(dbp)
            bot.skills["clean"].run(p, dest, args.keep_float, **params)
        else:
            clean_audio(str(p), str(dest), target_lufs=args.lufs, deess=not args.no_deess)
        count += 1
    print(f"Processed {count} files -> {out_dir}")
    return 0


def cmd_stems(args: argparse.Namespace) -> int:
    inp = Path(args.input)
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    ok = separate_stems(str(inp), str(out_dir))
    if not ok:
        print("Warning: demucs not available; no stems created.")
    else:
        print(f"Stems in {out_dir}")
    return 0


def cmd_serve_web(args: argparse.Namespace) -> int:
    try:
        import uvicorn  # type: ignore
    except Exception as e:
        print(f"uvicorn not available: {e}")
        return 2
    host = args.host
    port = args.port
    uvicorn.run("audiobot.web.app:app", host=host, port=port, reload=False)
    return 0


def cmd_serve_lit(args: argparse.Namespace) -> int:
    try:
        import uvicorn  # type: ignore
    except Exception as e:
        print(f"uvicorn not available: {e}")
        return 2
    host = args.host
    port = args.port
    uvicorn.run("audiobot.web.litserve_app:app", host=host, port=port, reload=False)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="audiobot", description="Holy Spirit Vocal Engine CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    pc = sub.add_parser("clean", help="Clean a single WAV file")
    pc.add_argument("input")
    pc.add_argument("-o", "--output", required=True)
    pc.add_argument("--lufs", type=float, default=-14.0)
    pc.add_argument("--no-deess", action="store_true")
    # FFmpeg preset path (optional)
    pc.add_argument("--preset", type=str, default="", help="FFmpeg preset: very_noisy_vox, very_loud_crispy, max_loudness or db:NAME")
    pc.add_argument("--air-bus", action="store_true", help="Enable AIR parallel bus (with --preset)")
    pc.add_argument("--air-mix", type=float, default=0.2, help="AIR bus mix 0..1 (with --preset)")
    pc.add_argument("--gate-thresh-db", type=float, default=-45.0, help="Gate threshold dB (preset)")
    pc.add_argument("--air-highpass", type=int, default=9500, help="AIR highpass Hz (preset)")
    pc.add_argument("--air-shelf-db", type=float, default=3.0, help="AIR shelf gain dB (preset)")
    pc.add_argument("--air-deess-strength", type=float, default=2.0, help="AIR de-ess strength 0..2 (preset)")
    pc.add_argument("--post-deess-center", type=float, default=0.35, help="Post-mix de-ess center 0..1")
    pc.add_argument("--post-deess-strength", type=float, default=0.0, help="Post-mix de-ess strength 0..2")
    pc.add_argument("--no-gate", action="store_true", help="Disable gate in preset chain")
    pc.add_argument("--no-declick", action="store_true", help="Disable adeclick in preset chain")
    pc.add_argument("--no-declip", action="store_true", help="Disable adeclip in preset chain")
    pc.add_argument("--keep-float", action="store_true", dest="keep_float", help="Preserve float PCM on output when using preset")
    # ML inference options (optional)
    pc.add_argument("--ml-model", type=str, default="", help="Path or gs:// to Torch/ONNX denoiser model")
    pc.add_argument("--ml-sample-rate", type=int, default=48000)
    pc.add_argument("--ml-chunk-seconds", type=float, default=1.0)
    pc.add_argument("--ml-overlap", type=float, default=0.1)
    pc.add_argument("--ml-device", type=str, default="", help="cpu or cuda (auto if empty)")
    pc.set_defaults(func=cmd_clean)

    pb = sub.add_parser("batch", help="Batch process all WAVs in a folder")
    pb.add_argument("input")
    pb.add_argument("-o", "--output", required=True)
    pb.add_argument("--lufs", type=float, default=-14.0)
    pb.add_argument("--no-deess", action="store_true")
    pb.add_argument("--preset", type=str, default="", help="FFmpeg preset: very_noisy_vox, very_loud_crispy, max_loudness or db:NAME")
    pb.add_argument("--air-bus", action="store_true")
    pb.add_argument("--air-mix", type=float, default=0.2)
    pb.add_argument("--gate-thresh-db", type=float, default=-45.0)
    pb.add_argument("--air-highpass", type=int, default=9500)
    pb.add_argument("--air-shelf-db", type=float, default=3.0)
    pb.add_argument("--air-deess-strength", type=float, default=2.0)
    pb.add_argument("--post-deess-center", type=float, default=0.35)
    pb.add_argument("--post-deess-strength", type=float, default=0.0)
    pb.add_argument("--no-gate", action="store_true")
    pb.add_argument("--no-declick", action="store_true")
    pb.add_argument("--no-declip", action="store_true")
    pb.add_argument("--keep-float", action="store_true", dest="keep_float")
    # ML inference options (optional)
    pb.add_argument("--ml-model", type=str, default="")
    pb.add_argument("--ml-sample-rate", type=int, default=48000)
    pb.add_argument("--ml-chunk-seconds", type=float, default=1.0)
    pb.add_argument("--ml-overlap", type=float, default=0.1)
    pb.add_argument("--ml-device", type=str, default="")
    pb.set_defaults(func=cmd_batch)

    ps = sub.add_parser("stems", help="Demucs stem separation (if available)")
    ps.add_argument("input")
    ps.add_argument("-o", "--output", required=True)
    ps.set_defaults(func=cmd_stems)

    pw = sub.add_parser("serve-web", help="Run FastAPI web server")
    pw.add_argument("-H", "--host", default="127.0.0.1")
    pw.add_argument("-p", "--port", type=int, default=8000)
    pw.set_defaults(func=cmd_serve_web)

    pl = sub.add_parser("serve-lit", help="Run Lite web app for agent endpoints")
    pl.add_argument("-H", "--host", default="127.0.0.1")
    pl.add_argument("-p", "--port", type=int, default=8080)
    pl.set_defaults(func=cmd_serve_lit)

    # Video: download by URL
    pvd = sub.add_parser("video-dl", help="Download a video by URL (yt-dlp)")
    pvd.add_argument("url")
    pvd.add_argument("-o", "--output", default="web/uploads")
    def _cmd_vd(a: argparse.Namespace) -> int:
        bot = Bot()
        res = bot.skills["download"].run(a.url, a.output)
        if not res.get("ok"):
            print("Download failed:", res.get("log", ""))
            return 2
        print("Downloaded ->", res.get("path"))
        return 0
    pvd.set_defaults(func=_cmd_vd)

    # Video: download and extract audio WAV
    pva = sub.add_parser("video-audio", help="Download video by URL and extract audio to WAV")
    pva.add_argument("url")
    pva.add_argument("-o", "--output", default="web/outputs")
    def _cmd_va(a: argparse.Namespace) -> int:
        bot = Bot()
        d = bot.skills["download"].run(a.url, "web/uploads")
        if not d.get("ok") or not d.get("path"):
            print("Download failed:", d.get("log", ""))
            return 2
        src = Path(d["path"])  # type: ignore[index]
        out_dir = Path(a.output)
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / f"{src.stem}.wav"
        e = bot.skills["extract"].run(src, out)
        if not e.get("ok"):
            print("Extract failed:", e.get("log", ""))
            return 2
        print("Audio ->", e.get("output"))
        return 0
    pva.set_defaults(func=_cmd_va)

    # Video: download, extract, then separate stems if available
    pvs = sub.add_parser("video-separate", help="Download video URL, extract audio, then Demucs stems")
    pvs.add_argument("url")
    pvs.add_argument("-o", "--output", default="web/outputs")
    def _cmd_vs(a: argparse.Namespace) -> int:
        bot = Bot()
        d = bot.skills["download"].run(a.url, "web/uploads")
        if not d.get("ok") or not d.get("path"):
            print("Download failed:", d.get("log", ""))
            return 2
        src = Path(d["path"])  # type: ignore[index]
        out_dir = Path(a.output)
        out_dir.mkdir(parents=True, exist_ok=True)
        wav = out_dir / f"{src.stem}.wav"
        e = bot.skills["extract"].run(src, wav)
        if not e.get("ok"):
            print("Extract failed:", e.get("log", ""))
            return 2
        ok = separate_stems(str(wav), str(out_dir))
        if not ok:
            print("Warning: demucs not available; no stems created.")
            return 2
        print(f"Stems in {out_dir}")
        return 0
    pvs.set_defaults(func=_cmd_vs)

    # Local ML training: denoiser for very noisy/sibilant audio
    ptn = sub.add_parser("train-noise", help="Train denoiser locally (PyTorch Lightning)")
    ptn.add_argument("--clean-dir", required=True)
    ptn.add_argument("--noisy-dir", default="")
    ptn.add_argument("--batch-size", type=int, default=16)
    ptn.add_argument("--workers", type=int, default=2)
    ptn.add_argument("--epochs", type=int, default=5)
    ptn.add_argument("--sample-rate", type=int, default=48000)
    ptn.add_argument("--chunk-seconds", type=float, default=1.0)
    ptn.add_argument("--lr", type=float, default=1e-3)
    ptn.add_argument("--outdir", default="web/outputs/models")
    ptn.add_argument("--save-onnx", action="store_true")
    def _cmd_train_noise(a: argparse.Namespace) -> int:
        try:
            from .pipeline.train_noise import main as train_main  # type: ignore
        except Exception as e:
            print("Training deps missing. Install torch, pytorch-lightning, torchaudio, librosa, soundfile.")
            print(e)
            return 2
        argv = [
            "--clean-dir", a.clean_dir,
        ]
        if a.noisy_dir:
            argv += ["--noisy-dir", a.noisy_dir]
        argv += [
            "--batch-size", str(a.batch_size),
            "--workers", str(a.workers),
            "--epochs", str(a.epochs),
            "--sample-rate", str(a.sample_rate),
            "--chunk-seconds", str(a.chunk_seconds),
            "--lr", str(a.lr),
            "--outdir", a.outdir,
        ]
        if a.save_onnx:
            argv.append("--save-onnx")
        return train_main(argv)
    ptn.set_defaults(func=_cmd_train_noise)

    # Vertex AI training job submission
    pvx = sub.add_parser("vertex-train-noise", help="Submit Vertex AI CustomTrainingJob for denoiser")
    pvx.add_argument("--project", required=True)
    pvx.add_argument("--region", required=True)
    pvx.add_argument("--staging-bucket", required=True, help="gs://BUCKET")
    pvx.add_argument("--display-name", default="audiobot-denoiser-train")
    pvx.add_argument("--machine-type", default="n1-standard-8")
    pvx.add_argument("--accelerator-type", default="", help="e.g., NVIDIA_TESLA_T4 or leave empty")
    pvx.add_argument("--accelerator-count", type=int, default=1)
    # Training script args (use GCS URIs ideally)
    pvx.add_argument("--clean-dir", required=True, help="Local or gs:// path")
    pvx.add_argument("--noisy-dir", default="")
    pvx.add_argument("--batch-size", type=int, default=32)
    pvx.add_argument("--workers", type=int, default=4)
    pvx.add_argument("--epochs", type=int, default=5)
    pvx.add_argument("--sample-rate", type=int, default=48000)
    pvx.add_argument("--chunk-seconds", type=float, default=1.0)
    pvx.add_argument("--lr", type=float, default=1e-3)
    pvx.add_argument("--outdir", default="/root/audiobot_work/models")
    pvx.add_argument("--save-onnx", action="store_true")
    def _cmd_vertex_train(a: argparse.Namespace) -> int:
        try:
            from .pipeline.vertex_job import VertexConfig, submit_vertex_job  # type: ignore
        except Exception as e:
            print("Vertex SDK missing. Install google-cloud-aiplatform.")
            print(e)
            return 2
        cfg = VertexConfig(
            project=a.project,
            region=a.region,
            staging_bucket=a.staging_bucket,
            display_name=a.display_name,
            machine_type=a.machine_type,
            accelerator_type=(a.accelerator_type or None),
            accelerator_count=a.accelerator_count,
        )
        script_args = [
            "--clean-dir", a.clean_dir,
        ]
        if a.noisy_dir:
            script_args += ["--noisy-dir", a.noisy_dir]
        script_args += [
            "--batch-size", str(a.batch_size),
            "--workers", str(a.workers),
            "--epochs", str(a.epochs),
            "--sample-rate", str(a.sample_rate),
            "--chunk-seconds", str(a.chunk_seconds),
            "--lr", str(a.lr),
            "--outdir", a.outdir,
        ]
        if a.save_onnx:
            script_args.append("--save-onnx")
        job_name = submit_vertex_job(cfg, script_args)
        print("Submitted Vertex job:", job_name)
        return 0
    pvx.set_defaults(func=_cmd_vertex_train)

    # Explicit denoise inference command
    pdi = sub.add_parser("infer-noise", help="Run ML denoiser on a file")
    pdi.add_argument("input")
    pdi.add_argument("-o", "--output", required=True)
    pdi.add_argument("--ml-model", required=True)
    pdi.add_argument("--ml-sample-rate", type=int, default=48000)
    pdi.add_argument("--ml-chunk-seconds", type=float, default=1.0)
    pdi.add_argument("--ml-overlap", type=float, default=0.1)
    pdi.add_argument("--ml-device", type=str, default="")
    def _cmd_infer_noise(a: argparse.Namespace) -> int:
        bot = Bot()
        res = bot.skills["denoise"].run(
            Path(a.input),
            Path(a.output),
            model_path=a.ml_model,
            sample_rate=a.ml_sample_rate,
            chunk_seconds=a.ml_chunk_seconds,
            overlap_seconds=a.ml_overlap,
            device=(a.ml_device or None),
        )
        if not res.get("ok"):
            print("Denoise failed:", res.get("log", ""))
            return 2
        print("Denoised ->", res.get("output"))
        return 0
    pdi.set_defaults(func=_cmd_infer_noise)

    return p


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
