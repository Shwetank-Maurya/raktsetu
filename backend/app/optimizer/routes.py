"""Travel-time matrix: Google Routes API computeRouteMatrix (traffic-aware) with an in-memory
cache, falling back to haversine x road factor when the key is missing or the call fails."""

from __future__ import annotations

import logging
import math
import time

import httpx

from app.config import get_settings

log = logging.getLogger(__name__)

ROAD_FACTOR = 1.35
URBAN_KMH = 28.0
HANDLING_MIN = 15.0  # packing + cold-box handover
_CACHE: dict[tuple, tuple[float, float, float, str]] = {}  # key -> (expires, minutes, km, source)
CACHE_TTL_S = 30 * 60


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(h))


def fallback_eta(a: tuple[float, float], b: tuple[float, float]) -> tuple[float, float]:
    km = haversine_km(a, b) * ROAD_FACTOR
    return km / URBAN_KMH * 60 + HANDLING_MIN, km


def _key(a, b) -> tuple:
    return (round(a[0], 4), round(a[1], 4), round(b[0], 4), round(b[1], 4))


async def eta_matrix(
    origins: list[tuple[float, float]], destinations: list[tuple[float, float]], use_api: bool = True,
) -> dict[tuple[int, int], tuple[float, float, str]]:
    """Returns {(i, j): (minutes, km, source)} for every origin/destination pair."""
    now = time.time()
    out: dict[tuple[int, int], tuple[float, float, str]] = {}
    missing: list[tuple[int, int]] = []
    for i, a in enumerate(origins):
        for j, b in enumerate(destinations):
            hit = _CACHE.get(_key(a, b))
            if hit and hit[0] > now:
                out[(i, j)] = (hit[1], hit[2], hit[3])
            else:
                missing.append((i, j))
    key = get_settings().maps_server_key
    if missing and key and use_api:
        try:
            await _routes_api(origins, destinations, missing, key, out)
        except Exception as exc:  # noqa: BLE001 - quota/network failure -> haversine (edge case #27)
            log.warning("Routes API failed, using haversine fallback: %s", exc)
    for i, j in missing:
        if (i, j) not in out:
            m, km = fallback_eta(origins[i], destinations[j])
            out[(i, j)] = (m, km, "haversine")
    return out


async def _routes_api(origins, destinations, missing, key, out) -> None:
    oi = sorted({i for i, _ in missing})
    dj = sorted({j for _, j in missing})
    wp = lambda p: {"waypoint": {"location": {"latLng": {"latitude": p[0], "longitude": p[1]}}}}  # noqa: E731
    # Routes API: <= 625 elements per TRAFFIC_AWARE request. Chunk origins accordingly.
    chunk = max(1, 625 // max(1, len(dj)))
    async with httpx.AsyncClient(timeout=15) as c:
        for s in range(0, len(oi), chunk):
            o_part = oi[s: s + chunk]
            r = await c.post(
                "https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix",
                headers={"X-Goog-Api-Key": key,
                         "X-Goog-FieldMask": "originIndex,destinationIndex,duration,distanceMeters,condition"},
                json={"origins": [wp(origins[i]) for i in o_part], "destinations": [wp(destinations[j]) for j in dj],
                      "travelMode": "DRIVE", "routingPreference": "TRAFFIC_AWARE"},
            )
            r.raise_for_status()
            now = time.time()
            for el in r.json():
                if el.get("condition") != "ROUTE_EXISTS":
                    continue
                i, j = o_part[el["originIndex"]], dj[el["destinationIndex"]]
                minutes = float(el["duration"].rstrip("s")) / 60 + HANDLING_MIN
                km = el.get("distanceMeters", 0) / 1000
                out[(i, j)] = (minutes, km, "routes_api")
                _CACHE[_key(origins[i], destinations[j])] = (now + CACHE_TTL_S, minutes, km, "routes_api")
