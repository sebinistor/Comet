"""Provider interfaces.

Keeping these tiny and explicit lets the mock providers stand in for the real
cloud services in tests / demo mode, and leaves room for a future local-Emporia
(ESPHome) meter source without touching the ingest or costing code.
"""

from __future__ import annotations

import datetime as dt
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(slots=True)
class PriceSample:
    ts_utc: dt.datetime
    price_cents: float  # cents per kWh
    kind: str  # "5min" | "hour_avg"


@dataclass(slots=True)
class ConsumptionSample:
    ts_utc: dt.datetime
    device_gid: str
    kwh: float  # energy consumed during the sample's minute


class PriceProvider(ABC):
    @abstractmethod
    async def recent_five_minute(
        self, start: dt.datetime | None = None, end: dt.datetime | None = None
    ) -> list[PriceSample]:
        """5-minute real-time market prices. No bounds => trailing 24h."""

    @abstractmethod
    async def current_hour_average(self) -> PriceSample:
        """The current hour's billed-basis average price."""


class MeterProvider(ABC):
    @abstractmethod
    async def latest_minute(self) -> list[ConsumptionSample]:
        """Most recent completed 1-minute kWh bucket, one row per device GID."""

    @abstractmethod
    async def instant_watts(self) -> float:
        """Best-effort instantaneous total draw in watts (for the live tile)."""

    @abstractmethod
    async def backfill_hourly(
        self, start: dt.datetime, end: dt.datetime
    ) -> list[ConsumptionSample]:
        """Historical hourly kWh for seeding rollups on first run."""
