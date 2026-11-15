"""NOAA SWPC GOES proton flux, cached, with a plausible fallback when offline."""
import time
from datetime import datetime, timezone

import httpx

URL = "https://services.swpc.noaa.gov/json/goes/primary/integral-protons-1-day.json"
CACHE_SECONDS = 300
TIMEOUT = 5.0
# S1..S5 start at these >=10 MeV proton fluxes (pfu)
S_SCALE_STEPS = [10, 100, 1_000, 10_000, 100_000]

_cache = {"at": 0.0, "data": None}


def s_scale(flux):
    return sum(flux >= step for step in S_SCALE_STEPS)


async def _fetch():
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.get(URL)
        response.raise_for_status()
    latest = [row for row in response.json() if row["energy"] == ">=10 MeV"][-1]
    flux = float(latest["flux"])
    return {"source": "NOAA SWPC GOES", "proton_flux_pfu": flux, "s_scale": s_scale(flux),
            "updated": latest["time_tag"]}


async def get_spaceweather():
    if _cache["data"] and time.monotonic() - _cache["at"] < CACHE_SECONDS:
        return _cache["data"]
    try:
        data = await _fetch()
    except (httpx.HTTPError, ValueError, KeyError, IndexError):
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        data = {"source": "fallback", "proton_flux_pfu": 0.3, "s_scale": 0, "updated": now}
    _cache.update(at=time.monotonic(), data=data)
    return data
