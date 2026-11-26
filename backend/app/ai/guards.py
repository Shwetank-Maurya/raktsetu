"""Grounding guards. Gemini may only state numbers that appear in tool results (edge case #31),
and untrusted text (notes, OCR) is fenced as data (edge case #32)."""

from __future__ import annotations

import json
import re

_NUM = re.compile(r"(?<![\w.])-?\d+(?:[.,]\d+)?%?")
# Small integers and list ordinals appear in natural language ("top 3", "24 hours") and are allowed.
ALLOWED_FREE = {str(i) for i in range(0, 11)} | {"24", "48", "72", "100"}
_DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")


def _collect_numbers(obj, out: set[float]) -> None:
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        out.add(round(float(obj), 6))
        if isinstance(obj, float) and 0 <= obj <= 1:
            out.add(round(obj * 100, 6))  # probabilities may be stated as percentages
    elif isinstance(obj, dict):
        for v in obj.values():
            _collect_numbers(v, out)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _collect_numbers(v, out)
    elif isinstance(obj, str):
        for m in _NUM.findall(obj):
            try:
                out.add(round(float(m.rstrip("%").replace(",", "")), 6))
            except ValueError:
                pass


def numbers_in_text(text: str) -> list[str]:
    text = text.translate(_DEVANAGARI_DIGITS)
    # ignore ISO dates/times, e.g. 2026-11-26 or 14:00
    text = re.sub(r"\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?)?", " ", text)
    text = re.sub(r"\b\d{1,2}:\d{2}\b", " ", text)
    text = re.sub(r"\b[A-Z]{2}-\d{2}\b", " ", text)  # facility codes like LH-03
    return _NUM.findall(text)


def _matches(value: float, allowed: set[float]) -> bool:
    for a in allowed:
        tol = max(0.51, abs(a) * 0.01)  # rounding to integers / 1% is acceptable
        if abs(a - value) <= tol:
            return True
    return False


def numeric_check(answer: str, tool_payloads: list) -> tuple[bool, list[str]]:
    """Every number in the answer must match (within rounding) a number from the tool JSON."""
    allowed: set[float] = set()
    for p in tool_payloads:
        _collect_numbers(p, allowed)
    bad = []
    for tok in numbers_in_text(answer):
        raw = tok.rstrip("%").replace(",", "")
        if raw.lstrip("-") in ALLOWED_FREE:
            continue
        try:
            v = float(raw)
        except ValueError:
            continue
        if not _matches(v, allowed):
            bad.append(tok)
    return (not bad), bad


def fence_untrusted(text: str | None, limit: int = 500) -> str:
    """Wrap free text so the model treats it as data, never as instructions."""
    if not text:
        return ""
    clean = text.replace("```", "'''")[:limit]
    return f"<untrusted_data>{json.dumps(clean)}</untrusted_data>"


INJECTION_HINTS = re.compile(r"(ignore (all|previous)|system prompt|you are now|call (the )?tool|approve transfer)", re.I)


def looks_like_injection(text: str | None) -> bool:
    return bool(text and INJECTION_HINTS.search(text))
