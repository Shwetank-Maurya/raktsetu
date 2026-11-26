"""Seasonality inputs: festivals/holidays (Google Calendar API + static fallback table),
monsoon/dengue index (Open-Meteo rainfall when reachable, seasonal curve otherwise)."""

from __future__ import annotations

import logging
import math
from datetime import date, timedelta
from urllib.parse import quote

import httpx

from app.config import get_settings

log = logging.getLogger(__name__)

# Moving festivals (lunar calendars shift every year). Approximate; Google Calendar sync overrides.
# weight = relative bump in emergency (road-accident / trauma) demand around the date.
STATIC_FESTIVALS: list[tuple[str, str, float]] = [
    ("2025-01-01", "New Year", 1.0), ("2025-01-26", "Republic Day", 0.5), ("2025-03-14", "Holi", 1.2),
    ("2025-03-31", "Eid al-Fitr", 0.8), ("2025-06-07", "Eid al-Adha", 0.6), ("2025-08-09", "Raksha Bandhan", 0.6),
    ("2025-08-15", "Independence Day", 0.6), ("2025-08-16", "Janmashtami", 0.5), ("2025-10-02", "Dussehra", 1.0),
    ("2025-10-20", "Diwali", 1.5), ("2025-12-25", "Christmas", 0.6), ("2025-12-31", "New Year's Eve", 1.2),
    ("2026-01-01", "New Year", 1.0), ("2026-01-26", "Republic Day", 0.5), ("2026-03-04", "Holi", 1.2),
    ("2026-03-20", "Eid al-Fitr", 0.8), ("2026-05-27", "Eid al-Adha", 0.6), ("2026-08-15", "Independence Day", 0.6),
    ("2026-08-28", "Raksha Bandhan", 0.6), ("2026-09-04", "Janmashtami", 0.5), ("2026-10-20", "Dussehra", 1.0),
    ("2026-11-08", "Diwali", 1.5), ("2026-12-25", "Christmas", 0.6), ("2026-12-31", "New Year's Eve", 1.2),
    ("2027-01-01", "New Year", 1.0), ("2027-01-26", "Republic Day", 0.5), ("2027-03-10", "Eid al-Fitr", 0.8),
    ("2027-03-22", "Holi", 1.2), ("2027-10-09", "Dussehra", 1.0), ("2027-10-29", "Diwali", 1.5),
]

FESTIVAL_WEIGHTS = {"diwali": 1.5, "holi": 1.2, "new year": 1.0, "dussehra": 1.0, "eid": 0.8}


def static_festivals() -> dict[date, tuple[str, float]]:
    return {date.fromisoformat(d): (n, w) for d, n, w in STATIC_FESTIVALS}


def festival_proximity(day: date, festivals: dict[date, tuple[str, float]], window: int = 3) -> tuple[float, str | None]:
    """Triangular kernel: full weight on the day, decaying over +/- window days."""
    best, name = 0.0, None
    for off in range(-window, window + 1):
        hit = festivals.get(day + timedelta(days=off))
        if hit:
            v = hit[1] * (1 - abs(off) / (window + 1))
            if v > best:
                best, name = v, hit[0]
    return best, name


def dengue_index(day: date) -> float:
    """0..1 seasonal dengue pressure for North India: rises with monsoon, peaks late Sep - Oct."""
    doy = day.timetuple().tm_yday
    return math.exp(-(((doy - 280) / 32) ** 2))


def monsoon_index(day: date) -> float:
    doy = day.timetuple().tm_yday
    return math.exp(-(((doy - 215) / 35) ** 2))


async def fetch_google_holidays(start: date, end: date) -> list[dict]:
    """Public holidays from Google Calendar API (needs only an API key; free)."""
    s = get_settings()
    if not s.google_calendar_api_key:
        return []
    url = f"https://www.googleapis.com/calendar/v3/calendars/{quote(s.holiday_calendar_id, safe='')}/events"
    params = {
        "key": s.google_calendar_api_key, "timeMin": f"{start.isoformat()}T00:00:00Z",
        "timeMax": f"{end.isoformat()}T00:00:00Z", "singleEvents": "true", "maxResults": 250,
    }
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(url, params=params)
            r.raise_for_status()
        out = []
        for item in r.json().get("items", []):
            d = item.get("start", {}).get("date")
            name = item.get("summary", "Holiday")
            if not d:
                continue
            w = next((v for k, v in FESTIVAL_WEIGHTS.items() if k in name.lower()), 0.4)
            out.append({"date": date.fromisoformat(d), "name": name, "weight": w})
        return out
    except Exception as exc:  # noqa: BLE001 - external API is optional
        log.warning("google calendar fetch failed, using static table: %s", exc)
        return []


async def fetch_rainfall_index(lat: float, lng: float) -> float | None:
    """Open-Meteo past-21-day rainfall -> 0..1 index (lagged driver for dengue). Optional."""
    try:
        async with httpx.AsyncClient(timeout=8) as c:
            r = await c.get("https://api.open-meteo.com/v1/forecast", params={
                "latitude": lat, "longitude": lng, "daily": "precipitation_sum",
                "past_days": 21, "forecast_days": 1, "timezone": "Asia/Kolkata"})
            r.raise_for_status()
        vals = [v or 0 for v in r.json()["daily"]["precipitation_sum"]]
        return min(1.0, sum(vals) / 250.0)
    except Exception as exc:  # noqa: BLE001
        log.info("open-meteo unavailable: %s", exc)
        return None
