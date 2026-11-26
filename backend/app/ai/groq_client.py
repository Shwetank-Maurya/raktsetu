"""Groq fallback LLM (OpenAI-compatible chat completions with tool calling).

Used only when Gemini is unavailable (overloaded / quota / outage). Same grounding rules apply:
read-only tools, numeric post-check, template answer if anything fails. Free tier, no card.
"""

from __future__ import annotations

import logging
import time

import httpx

from app.config import get_settings

log = logging.getLogger(__name__)
_failures: list[float] = []


class GroqUnavailable(Exception):
    pass


def enabled() -> bool:
    return bool(get_settings().groq_api_key)


async def chat(messages: list[dict], tools: list[dict] | None = None, json_mode: bool = False,
               temperature: float = 0.2, max_tokens: int = 900) -> dict:
    """Returns the assistant message dict ({content, tool_calls?})."""
    s = get_settings()
    if not s.groq_api_key:
        raise GroqUnavailable("Groq not configured")
    now = time.time()
    _failures[:] = [t for t in _failures if now - t < 120]
    if len(_failures) >= 3:
        raise GroqUnavailable("circuit open after repeated Groq failures")
    body: dict = {"model": s.groq_model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
    if tools:
        body |= {"tools": tools, "tool_choice": "auto"}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    try:
        async with httpx.AsyncClient(timeout=40) as c:
            r = await c.post(f"{s.groq_base_url.rstrip('/')}/chat/completions",
                             headers={"Authorization": f"Bearer {s.groq_api_key}"}, json=body)
        if r.status_code >= 400:
            raise GroqUnavailable(f"{r.status_code} {r.text[:200]}")
        return r.json()["choices"][0]["message"]
    except GroqUnavailable:
        _failures.append(time.time())
        raise
    except Exception as exc:  # noqa: BLE001
        _failures.append(time.time())
        log.warning("groq call failed: %s", exc)
        raise GroqUnavailable(str(exc)) from exc


def status() -> dict:
    s = get_settings()
    return {"enabled": enabled(), "model": s.groq_model, "breaker_open": len(_failures) >= 3}
