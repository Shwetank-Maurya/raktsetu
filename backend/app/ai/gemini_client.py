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


_last_model: str | None = None


def _transient(exc: Exception) -> bool:
    """Capacity / rate errors worth retrying on another model (503 overloaded, 429 quota, timeouts)."""
    msg = str(exc)
    return any(t in msg for t in ("503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED", "overloaded", "high demand", "DEADLINE"))


def model_chain(model: str | None = None) -> list[str]:
    s = get_settings()
    chain = [model or s.gemini_model] + [m.strip() for m in s.gemini_model_fallbacks.split(",") if m.strip()]
    return list(dict.fromkeys(chain))


async def generate(contents, config, model: str | None = None):
    """Try the configured model, then fallbacks on transient capacity errors (503/429), with one
    short backoff. Only a full-chain failure counts toward the circuit breaker."""
    import asyncio

    global _last_model
    _check_breaker()
    client = get_client()
    last_exc: Exception | None = None
    for i, m in enumerate(model_chain(model)):
        for attempt in range(2 if i == 0 else 1):
            try:
                resp = await asyncio.wait_for(
                    client.aio.models.generate_content(model=m, contents=contents, config=config), timeout=45)
                if m != _last_model:
                    log.info("gemini answering with %s", m)
                _last_model = m
                return resp
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                if not _transient(exc):
                    _failures.append(time.time())
                    log.warning("gemini call failed (%s): %s", m, exc)
                    raise GeminiUnavailable(str(exc)) from exc
                log.info("gemini %s busy (%s), %s", m, str(exc)[:60], "retrying" if attempt == 0 and i == 0 else "trying next model")
                if attempt == 0 and i == 0:
                    await asyncio.sleep(1.5)
    _failures.append(time.time())
    log.warning("gemini unavailable on all models %s: %s", model_chain(model), last_exc)
    raise GeminiUnavailable(str(last_exc))


def status() -> dict:
    s = get_settings()
    return {"enabled": s.gemini_enabled, "mode": "vertex" if s.google_genai_use_vertexai else ("ai_studio" if s.gemini_api_key else "off"),
            "model": s.gemini_model, "fallbacks": model_chain()[1:], "last_model_used": _last_model,
            "breaker_open": len(_failures) >= BREAKER_THRESHOLD}
