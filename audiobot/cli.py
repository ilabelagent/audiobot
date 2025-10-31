import argparse
import sys
from pathlib import Path

from .processing.clean import clean_audio
from .stems.demucs import separate_stems


def cmd_clean(args: argparse.Namespace) -> int:
    inp = Path(args.input)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
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
    pc.set_defaults(func=cmd_clean)

    pb = sub.add_parser("batch", help="Batch process all WAVs in a folder")
    pb.add_argument("input")
    pb.add_argument("-o", "--output", required=True)
    pb.add_argument("--lufs", type=float, default=-14.0)
    pb.add_argument("--no-deess", action="store_true")
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

    return p


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
