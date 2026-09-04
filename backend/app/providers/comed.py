"""ComEd Hourly Pricing API client.

Docs: https://hourlypricing.comed.com/hp-api/
No authentication. Prices are returned in cents per kWh as strings.
"""

from __future__ import annotations

import datetime as dt
import logging

import httpx

from app.providers.base import PriceProvider, PriceSample

_LOG = logging.getLogger("comet.comed")

API_URL = "https://hourlypricing.comed.com/api"
_TS_FMT = "%Y%m%d%H%M"


def _parse_feed(payload: list[dict], kind: str) -> list[PriceSample]:
    out: list[PriceSample] = []
    for row in payload:
        try:
            millis = int(row["millisUTC"])
            price = float(row["price"])
        except (KeyError, ValueError, TypeError):
            continue
        ts = dt.datetime.fromtimestamp(millis / 1000, tz=dt.timezone.utc)
        out.append(PriceSample(ts_utc=ts, price_cents=price, kind=kind))
    out.sort(key=lambda s: s.ts_utc)
    return out


class ComEdPriceProvider(PriceProvider):
    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client
        self._owns_client = client is None

    async def _get(self, params: dict[str, str]) -> list[dict]:
        params = {"format": "json", **params}
        client = self._client or httpx.AsyncClient(timeout=20.0)
        try:
            resp = await client.get(API_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
            return data if isinstance(data, list) else []
        finally:
            if self._owns_client:
                await client.aclose()

    async def recent_five_minute(
        self, start: dt.datetime | None = None, end: dt.datetime | None = None
    ) -> list[PriceSample]:
        params: dict[str, str] = {"type": "5minutefeed"}
        if start and end:
            params["datestart"] = start.astimezone(dt.timezone.utc).strftime(_TS_FMT)
            params["dateend"] = end.astimezone(dt.timezone.utc).strftime(_TS_FMT)
        payload = await self._get(params)
        samples = _parse_feed(payload, "5min")
        _LOG.debug("comed 5minutefeed: %d samples", len(samples))
        return samples

    async def current_hour_average(self) -> PriceSample:
        payload = await self._get({"type": "currenthouraverage"})
        samples = _parse_feed(payload, "hour_avg")
        if not samples:
            raise RuntimeError("ComEd currenthouraverage returned no data")
        return samples[-1]
