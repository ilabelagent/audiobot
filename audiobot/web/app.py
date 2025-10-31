from __future__ import annotations

import base64
import io
import zipfile
from pathlib import Path
import shutil
from typing import List, Optional

from fastapi import FastAPI, UploadFile, File, Form, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from audiobot.config import SETTINGS
import requests  # type: ignore
from audiobot.core import Bot
from audiobot.memory import Memory
from audiobot.ai import Advisor
from audiobot.processing.clean import clean_audio as py_clean_audio


def _auth_dep(authorization: str | None = Header(default=None)):
    token = SETTINGS.bearer_token.strip()
    if not token or token == "change-me":
        return  # auth disabled by default token
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    incoming = authorization.split(" ", 1)[1].strip()
    if incoming != token:
        raise HTTPException(status_code=401, detail="Invalid token")


app = FastAPI(title="Holy Spirit Vocal Engine API", dependencies=[Depends(_auth_dep)])

# Static and templates (served from package data)
pkg_dir = Path(__file__).parent
templates = Jinja2Templates(directory=str(pkg_dir / "templates"))
app.mount("/static", StaticFiles(directory=str(pkg_dir / "static")), name="static")

# Runtime I/O dirs (cwd-based)
UPLOADS_DIR = Path("web/uploads")
OUTPUTS_DIR = Path("web/outputs")
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

# Verses sources: user-extendable file and packaged defaults
VERSES_USER = Path("data/verses.txt")
VERSES_DEFAULT = pkg_dir / "verses_default.txt"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ui-config.json")
def ui_config():
    return {"verse_interval_sec": int(SETTINGS.verse_interval_sec)}


@app.get("/")
def index(request: Request):
    mem = Memory()
    presets = mem.list_presets()
    outputs = sorted([p.name for p in OUTPUTS_DIR.glob("*") if p.is_file()])[:100]
    return templates.TemplateResponse("index.html", {"request": request, "presets": presets, "outputs": outputs})


@app.get("/history")
def history(request: Request):
    mem = Memory()
    jobs = mem.list_jobs(limit=100)
    return templates.TemplateResponse("history.html", {"request": request, "jobs": jobs})


@app.get("/download/{name}")
def download(name: str):
    # Prevent path traversal
    safe = Path(name).name
    path = OUTPUTS_DIR / safe
    if not path.exists():
        raise HTTPException(status_code=404, detail="Not found")
    media = "application/octet-stream"
    try:
        if path.suffix.lower() in {".wav", ".flac", ".mp3", ".m4a", ".aiff", ".aif"}:
            media = "audio/wav" if path.suffix.lower() == ".wav" else media
    except Exception:
        pass
    return FileResponse(path, media_type=media, filename=path.name)


@app.get("/zip-stems/{base}")
def zip_stems(base: str):
    base_name = Path(base).name
    stems = list(OUTPUTS_DIR.glob(f"{base_name}_*.wav"))
    if not stems:
        raise HTTPException(status_code=404, detail="No stems found")
    zip_path = OUTPUTS_DIR / f"{base_name}_stems.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for s in stems:
            zf.write(s, arcname=s.name)
    return FileResponse(zip_path, media_type="application/zip", filename=zip_path.name)


@app.get("/verses.json")
def verses():
    items: list[str] = []
    seen: set[str] = set()
    # user-provided first (takes precedence)
    try:
        if VERSES_USER.exists():
            for line in VERSES_USER.read_text(encoding="utf-8").splitlines():
                t = line.strip()
                if t and t not in seen:
                    seen.add(t)
                    items.append(t)
    except Exception:
        pass
    # packaged defaults
    try:
        if VERSES_DEFAULT.exists():
            for line in VERSES_DEFAULT.read_text(encoding="utf-8").splitlines():
                t = line.strip()
                if t and t not in seen:
                    seen.add(t)
                    items.append(t)
    except Exception:
        pass
    # optional URL source for additional verses (one per line)
    url = os.getenv("AUDIOBOT_VERSES_URL", "").strip()
    if url:
        try:
            r = requests.get(url, timeout=3)
            if r.ok:
                for line in r.text.splitlines():
                    t = line.strip()
                    if t and t not in seen:
                        seen.add(t)
                        items.append(t)
        except Exception:
            pass
    if not items:
        items = ["Let everything that has breath praise the LORD. — Psalm 150:6"]
    return {"verses": items}


@app.post("/api/advice")
async def api_advice(file: UploadFile | None = File(default=None), context: str = Form("clean")):
    adv = Advisor()
    tmp = None
    if file is not None:
        tmp = UPLOADS_DIR / "advice_input.wav"
        tmp.write_bytes(await file.read())
    a = adv.suggest(file=tmp, stats=None, context=context)
    return {"ok": True, "source": a.source, "params": a.params, "notes": a.notes}


@app.post("/process")
async def process(
    request: Request,
    files: List[UploadFile] = File(...),
    noise_reduce: float = Form(12.0),
    noise_floor: float = Form(-28.0),
    deess_center: float = Form(0.25),
    deess_strength: float = Form(1.2),
    highpass: int = Form(70),
    lowpass: int = Form(18000),
    limiter: float = Form(0.95),
    keep_float: bool = Form(False),
    fast_mode: bool = Form(False),
    download: bool = Form(False),
):
    bot = Bot()
    results = []
    for f in files:
        raw = await f.read()
        in_name = f.filename or "input.wav"
        in_path = UPLOADS_DIR / in_name
        out_name = f"{Path(in_name).stem}_clean.wav"
        out_path = OUTPUTS_DIR / out_name
        in_path.write_bytes(raw)
        # Prefer ffmpeg chain if available; otherwise fallback to Python DSP cleaner
        if shutil.which("ffmpeg"):
            params = dict(
                noise_reduce=float(noise_reduce),
                noise_floor=float(noise_floor),
                deess_center=float(deess_center),
                deess_strength=float(deess_strength),
                highpass=int(highpass),
                lowpass=int(lowpass),
                limiter=float(limiter),
            )
            if fast_mode:
                # Lighter, faster defaults tuned for speed and transparency
                params["noise_reduce"] = min(params["noise_reduce"], 6.0)
                params["deess_strength"] = min(params["deess_strength"], 0.9)
                params["highpass"] = max(70, int(params["highpass"]))
                params["lowpass"] = max(19000, int(params["lowpass"]))
                params["limiter"] = max(0.98, float(params["limiter"]))
            res = bot.skills["clean"].run(in_path, out_path, keep_float, **params)
            ok = bool(res.get("ok"))
            log = str(res.get("log", ""))[-2000:]
        else:
            try:
                py_clean_audio(str(in_path), str(out_path), target_lufs=-14.0, deess=True)
                ok = True
                log = "python-clean"
            except Exception as e:
                ok = False
                log = str(e)
        results.append({
            "input": in_name,
            "ok": ok,
            "output": out_name if ok else None,
            "log": log,
        })
    # If a single file and download requested, stream it
    if download and len(results) == 1 and results[0].get("ok") and results[0].get("output"):
        p = OUTPUTS_DIR / str(results[0]["output"])
        data = p.read_bytes()
        return StreamingResponse(io.BytesIO(data), media_type="audio/wav", headers={
            "Content-Disposition": f"attachment; filename={p.name}"
        })
    # Otherwise render results page
    return templates.TemplateResponse("result.html", {"request": request, "results": results})


@app.post("/separate")
async def separate(request: Request, file: UploadFile = File(...), model: str = Form("htdemucs"), stems: int = Form(4), two_stems_target: str = Form("vocals")):
    bot = Bot()
    raw = await file.read()
    in_name = file.filename or "input.wav"
    in_path = UPLOADS_DIR / in_name
    in_path.write_bytes(raw)
    res = bot.skills["separate"].run(in_path, OUTPUTS_DIR, model=model, stems=int(stems), two_stems_target=two_stems_target)
    base = Path(in_name).stem
    out = {
        "input": in_name,
        "ok": bool(res.get("ok")),
        "stems": res.get("stems", []),
        "base": base,
        "log": str(res.get("log", ""))[-2000:],
    }
    return templates.TemplateResponse("result.html", {"request": request, "results": [out]})


@app.post("/batch")
async def batch(files: List[str], out_dir: Optional[str] = None):
    # Legacy JSON batch endpoint retained for compatibility
    bot = Bot()
    out = Path(out_dir or OUTPUTS_DIR)
    out.mkdir(parents=True, exist_ok=True)
    done = []
    for p in files:
        src = Path(p)
        dest = out / f"{src.stem}_clean.wav"
        res = bot.skills["clean"].run(src, dest, False)
        done.append({"path": str(dest), "ok": bool(res.get("ok"))})
    return {"outputs": done}


@app.post("/preset")
async def preset(name: str = Form(...), file: UploadFile = File(...)):
    dest = Path("presets") / f"{name}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(await file.read())
    return {"ok": True, "path": str(dest)}
