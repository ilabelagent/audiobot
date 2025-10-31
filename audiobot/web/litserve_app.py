from __future__ import annotations

from fastapi import FastAPI, Depends, Header, HTTPException
from audiobot.config import SETTINGS

def _auth_dep(authorization: str | None = Header(default=None)):
    token = SETTINGS.bearer_token.strip()
    if not token or token == "change-me":
        return
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    incoming = authorization.split(" ", 1)[1].strip()
    if incoming != token:
        raise HTTPException(status_code=401, detail="Invalid token")


app = FastAPI(title="HSVE Agent Lite", dependencies=[Depends(_auth_dep)])


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/lit/advice")
def advice(context: str = "clean"):
    if context.lower() == "clean":
        return {
            "chain": [
                "high-pass @ 60Hz",
                "de-ess 5-9kHz (mild)",
                "normalize to -14 LUFS",
                "true-peak ceiling -1dBFS",
            ]
        }
    return {"chain": ["analyze", "suggest profile", "apply"]}


@app.post("/lit/clean")
def lit_clean():
    return {"message": "Use /process on the main API to upload a file."}

