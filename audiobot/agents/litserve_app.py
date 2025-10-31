from __future__ import annotations

import base64
import io
from dataclasses import asdict
from pathlib import Path
from typing import Dict, Any

try:
    from litserve import LitServer, Endpoint  # type: ignore
    HAVE_LITSERVE = True
except Exception:
    HAVE_LITSERVE = False

from ..core import Bot
from ..ai import Advisor

if HAVE_LITSERVE:
    class AdviceEndpoint(Endpoint):
        def setup(self):
            self.bot = Bot()
            self.adv = Advisor()

        def predict(self, inp: Dict[str, Any]) -> Dict[str, Any]:
            context = inp.get("context", "clean")
            stats = inp.get("stats")
            file_b64 = inp.get("file_b64")
            tmp_file = None
            if file_b64:
                buf = base64.b64decode(file_b64)
                tmp_file = Path("web/uploads/advice_input.wav")
                tmp_file.parent.mkdir(parents=True, exist_ok=True)
                tmp_file.write_bytes(buf)
            advice = self.adv.suggest(file=tmp_file, stats=stats, context=context)
            return {"ok": True, "source": advice.source, "params": advice.params, "notes": advice.notes}

    class CleanEndpoint(Endpoint):
        def setup(self):
            self.bot = Bot()

        def predict(self, inp: Dict[str, Any]) -> Dict[str, Any]:
            file_b64 = inp.get("file_b64")
            params = inp.get("params", {})
            keep_float = bool(inp.get("keep_float", False))
            if not file_b64:
                return {"ok": False, "error": "missing file_b64"}
            buf = base64.b64decode(file_b64)
            in_path = Path("web/uploads/lit_in.wav")
            out_path = Path("web/outputs/lit_out_clean.wav")
            in_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            in_path.write_bytes(buf)
            res = self.bot.skills["clean"].run(in_path, out_path, keep_float, **params)
            if not res.get("ok"):
                return {"ok": False, "error": res.get("log", "")}
            out_b64 = base64.b64encode(out_path.read_bytes()).decode("utf-8")
            return {"ok": True, "file_b64": out_b64, "log": str(res.get("log", ""))[-2000:]}

    def build_server() -> "LitServer":
        return LitServer([AdviceEndpoint(), CleanEndpoint()], api_path="/lit")

else:
    from fastapi import FastAPI

    def build_server():
        # Provide a shim object with to_fastapi for CLI reuse
        class Shim:
            def to_fastapi(self):
                bot = Bot()
                adv = Advisor()
                app = FastAPI()

                @app.post("/lit/advice")
                def advice(inp: Dict[str, Any]):
                    context = inp.get("context", "clean")
                    stats = inp.get("stats")
                    file_b64 = inp.get("file_b64")
                    tmp_file = None
                    if file_b64:
                        buf = base64.b64decode(file_b64)
                        tmp_file = Path("web/uploads/advice_input.wav")
                        tmp_file.parent.mkdir(parents=True, exist_ok=True)
                        tmp_file.write_bytes(buf)
                    a = adv.suggest(file=tmp_file, stats=stats, context=context)
                    return {"ok": True, "source": a.source, "params": a.params, "notes": a.notes}

                @app.post("/lit/clean")
                def clean(inp: Dict[str, Any]):
                    file_b64 = inp.get("file_b64")
                    params = inp.get("params", {})
                    keep_float = bool(inp.get("keep_float", False))
                    if not file_b64:
                        return {"ok": False, "error": "missing file_b64"}
                    buf = base64.b64decode(file_b64)
                    in_path = Path("web/uploads/lit_in.wav")
                    out_path = Path("web/outputs/lit_out_clean.wav")
                    in_path.parent.mkdir(parents=True, exist_ok=True)
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    in_path.write_bytes(buf)
                    res = bot.skills["clean"].run(in_path, out_path, keep_float, **params)
                    if not res.get("ok"):
                        return {"ok": False, "error": res.get("log", "")}
                    out_b64 = base64.b64encode(out_path.read_bytes()).decode("utf-8")
                    return {"ok": True, "file_b64": out_b64, "log": str(res.get("log", ""))[-2000:]}

                return app

        return Shim()

if __name__ == "__main__":
    import uvicorn  # type: ignore
    server = build_server()
    app = server.to_fastapi()
    uvicorn.run(app, host="0.0.0.0", port=8080)
