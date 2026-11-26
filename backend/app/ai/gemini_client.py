"""Gemini access via the google-genai SDK.

Two auth paths, chosen by env:
- GEMINI_API_KEY (Google AI Studio free tier, no billing account needed)
- GOOGLE_GENAI_USE_VERTEXAI=true + ADC on Cloud Run (no key to leak)
A small in-process rate limiter and circuit breaker keep quota errors from cascading; callers
always have a template fallback (edge case #34)."""

from __future__ import annotations

import logging
import time

from app.config import get_settings

log = logging.getLogger(__name__)
_client = None
_failures: list[float] = []
_calls: list[float] = []
BREAKER_WINDOW_S = 120
BREAKER_THRESHOLD = 3
RATE_PER_MIN = 30


class GeminiUnavailable(Exception):
    pass


def get_client():
    global _client
    s = get_settings()
    if not s.gemini_enabled:
        raise GeminiUnavailable("Gemini not configured")
    if _client is None:
        from google import genai

        if s.google_genai_use_vertexai:
            _client = genai.Client(vertexai=True, project=s.google_cloud_project, location=s.google_cloud_location)
        else:
            _client = genai.Client(api_key=s.gemini_api_key)
    return _client


def _check_breaker() -> None:
    now = time.time()
    _failures[:] = [t for t in _failures if now - t < BREAKER_WINDOW_S]
    if len(_failures) >= BREAKER_THRESHOLD:
        raise GeminiUnavailable("circuit open after repeated Gemini failures")
    _calls[:] = [t for t in _calls if now - t < 60]
    if len(_calls) >= RATE_PER_MIN:
        raise GeminiUnavailable("local rate limit reached")
    _calls.append(now)


async def generate(contents, config, model: str | None = None):
    _check_breaker()
    client = get_client()
    try:
        return await client.aio.models.generate_content(
            model=model or get_settings().gemini_model, contents=contents, config=config)
    except Exception as exc:
        _failures.append(time.time())
        log.warning("gemini call failed: %s", exc)
        raise GeminiUnavailable(str(exc)) from exc


def status() -> dict:
    s = get_settings()
    return {"enabled": s.gemini_enabled, "mode": "vertex" if s.google_genai_use_vertexai else ("ai_studio" if s.gemini_api_key else "off"),
            "model": s.gemini_model, "breaker_open": len(_failures) >= BREAKER_THRESHOLD}
