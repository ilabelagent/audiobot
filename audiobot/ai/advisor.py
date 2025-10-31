from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from ..skills.inspect import analyze_audio


@dataclass
class Advice:
    params: Dict[str, Any]
    source: str
    notes: str = ""


class Advisor:
    def __init__(self) -> None:
        self.provider = os.getenv("AUDIOBOT_AI_PROVIDER", "heuristic").lower()

    def suggest(self, file: Optional[Path] = None, stats: Optional[Dict[str, Any]] = None, context: str = "clean") -> Advice:
        # Prefer explicit provider if configured
        if self.provider != "heuristic":
            adv = self._try_providers(file, stats, context)
            if adv:
                return adv
        # Fallback heuristic based on simple stats
        return self._heuristic(file, stats, context)

    def _try_providers(self, file: Optional[Path], stats: Optional[Dict[str, Any]], context: str) -> Optional[Advice]:
        prompt = self._make_prompt(stats or {}, context)
        b64 = None
        if file and Path(file).exists():
            try:
                b = Path(file).read_bytes()
                b64 = base64.b64encode(b).decode("utf-8")
            except Exception:
                b64 = None
        # Try OpenAI
        if os.getenv("OPENAI_API_KEY"):
            try:
                import openai  # type: ignore
                client = openai.OpenAI()
                content = prompt
                msg = client.chat.completions.create(
                    model=os.getenv("AUDIOBOT_OPENAI_MODEL", "gpt-4o-mini"),
                    messages=[{"role": "user", "content": content}],
                    temperature=0.2,
                )
                text = msg.choices[0].message.content or "{}"
                params = self._parse_json(text)
                if params:
                    return Advice(params=params, source="openai", notes="model: " + os.getenv("AUDIOBOT_OPENAI_MODEL", "gpt-4o-mini"))
            except Exception:
                pass
        # Try Anthropic
        if os.getenv("ANTHROPIC_API_KEY"):
            try:
                import anthropic  # type: ignore
                client = anthropic.Anthropic()
                text = client.messages.create(
                    model=os.getenv("AUDIOBOT_ANTHROPIC_MODEL", "claude-3-5-sonnet-latest"),
                    max_tokens=512,
                    messages=[{"role": "user", "content": prompt}],
                ).content[0].text
                params = self._parse_json(text)
                if params:
                    return Advice(params=params, source="anthropic", notes="model: " + os.getenv("AUDIOBOT_ANTHROPIC_MODEL", "claude-3-5-sonnet-latest"))
            except Exception:
                pass
        # Try Google Gemini
        if os.getenv("GOOGLE_API_KEY"):
            try:
                import google.generativeai as genai  # type: ignore
                genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
                model = genai.GenerativeModel(os.getenv("AUDIOBOT_GEMINI_MODEL", "gemini-1.5-flash"))
                resp = model.generate_content(prompt)
                text = resp.text or "{}"
                params = self._parse_json(text)
                if params:
                    return Advice(params=params, source="gemini", notes="model: " + os.getenv("AUDIOBOT_GEMINI_MODEL", "gemini-1.5-flash"))
            except Exception:
                pass
        return None

    def _heuristic(self, file: Optional[Path], stats: Optional[Dict[str, Any]], context: str) -> Advice:
        s = stats or {}
        if file and not stats:
            try:
                s = analyze_audio(Path(file))
            except Exception:
                s = {}
        rms = s.get("rms")
        peak = s.get("peak")
        # Base defaults
        params: Dict[str, Any] = dict(
            noise_reduce=12.0,
            noise_floor=-28.0,
            deess_center=0.25,
            deess_strength=1.2,
            highpass=70,
            lowpass=18000,
            limiter=0.95,
        )
        # Adjust for speech vs music
        if context == "podcast":
            params.update(dict(noise_reduce=14.0, noise_floor=-30.0, deess_center=0.22, deess_strength=1.4, highpass=80, lowpass=17000))
        # RMS/Peak guided tweaks
        if isinstance(rms, (int, float)) and rms < -25:
            params["limiter"] = 0.98
        if isinstance(peak, (int, float)) and peak > -1:
            params["limiter"] = 0.9
        return Advice(params=params, source="heuristic", notes="rule-based suggestion")

    def _make_prompt(self, stats: Dict[str, Any], context: str) -> str:
        return (
            "Suggest JSON only with FFmpeg filter params for transparent cleanup of sibilance/noise. "
            "Keys: noise_reduce, noise_floor, deess_center(0..1), deess_strength(0..2), highpass, lowpass, limiter(0..1). "
            f"Context: {context}. Stats: {json.dumps(stats)}."
        )

    def _parse_json(self, text: str) -> Optional[Dict[str, Any]]:
        try:
            # Try direct JSON
            return json.loads(text)
        except Exception:
            # Try to extract JSON block
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(text[start : end + 1])
                except Exception:
                    return None
        return None

