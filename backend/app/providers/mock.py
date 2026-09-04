"""Deterministic fake providers for demo mode (``COMET_MOCK=1``) and tests.

No network, no credentials. Values follow smooth daily curves so the dashboard
and rollups look realistic.
"""

from __future__ import annotations

import datetime as dt
import math

from app.providers.base import (
    ConsumptionSample,
    MeterProvider,
    PriceProvider,
    PriceSample,
)

_DEVICE = "mock-1"


def _price_cents(ts: dt.datetime) -> float:
    """Diurnal price curve, ~1.5..12 c/kWh, peaking late afternoon."""
    hour = ts.hour + ts.minute / 60.0
    base = 6.0 + 5.0 * math.sin((hour - 9.0) / 24.0 * 2 * math.pi)
    wobble = 0.6 * math.sin(ts.timestamp() / 900.0)
    return round(max(base + wobble, 0.5), 2)


def _kwh_for_minute(ts: dt.datetime) -> float:
    """Whole-home draw ~0.3..2.4 kW, higher morning and evening."""
    hour = ts.hour + ts.minute / 60.0
    morning = math.exp(-((hour - 7.5) ** 2) / 4.0)
    evening = math.exp(-((hour - 19.0) ** 2) / 6.0)
    kw = 0.35 + 1.4 * morning + 1.9 * evening + 0.15 * math.sin(ts.timestamp() / 600.0)
    return round(max(kw, 0.1) / 60.0, 5)


class MockPriceProvider(PriceProvider):
    async def recent_five_minute(
        self, start: dt.datetime | None = None, end: dt.datetime | None = None
    ) -> list[PriceSample]:
        end = end or dt.datetime.now(tz=dt.timezone.utc)
        start = start or (end - dt.timedelta(hours=24))
        start = start.replace(second=0, microsecond=0)
        start -= dt.timedelta(minutes=start.minute % 5)
        out: list[PriceSample] = []
        cursor = start
        while cursor <= end:
            out.append(PriceSample(ts_utc=cursor, price_cents=_price_cents(cursor), kind="5min"))
            cursor += dt.timedelta(minutes=5)
        return out

    async def current_hour_average(self) -> PriceSample:
        now = dt.datetime.now(tz=dt.timezone.utc).replace(minute=0, second=0, microsecond=0)
        samples = [_price_cents(now + dt.timedelta(minutes=m)) for m in range(0, 60, 5)]
        avg = round(sum(samples) / len(samples), 2)
        return PriceSample(ts_utc=now, price_cents=avg, kind="hour_avg")


class MockMeterProvider(MeterProvider):
    async def latest_minute(self) -> list[ConsumptionSample]:
        ts = dt.datetime.now(tz=dt.timezone.utc).replace(second=0, microsecond=0) - dt.timedelta(minutes=1)
        return [ConsumptionSample(ts_utc=ts, device_gid=_DEVICE, kwh=_kwh_for_minute(ts))]

    async def instant_watts(self) -> float:
        ts = dt.datetime.now(tz=dt.timezone.utc)
        return round(_kwh_for_minute(ts) * 60_000.0, 1)

    async def backfill_hourly(
        self, start: dt.datetime, end: dt.datetime
    ) -> list[ConsumptionSample]:
        start = start.replace(minute=0, second=0, microsecond=0)
        out: list[ConsumptionSample] = []
        cursor = start
        while cursor < end:
            kwh = sum(_kwh_for_minute(cursor + dt.timedelta(minutes=m)) for m in range(60))
            out.append(ConsumptionSample(ts_utc=cursor, device_gid=_DEVICE, kwh=round(kwh, 5)))
            cursor += dt.timedelta(hours=1)
        return out
