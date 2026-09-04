"""Background polling via APScheduler, running in the FastAPI event loop."""

from __future__ import annotations

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import get_settings
from app.providers import build_providers
from app.services import ingest

_LOG = logging.getLogger("comet.scheduler")


class Poller:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.price_provider, self.meter_provider = build_providers(self.settings)
        self.scheduler = AsyncIOScheduler(timezone="UTC")

    async def start(self) -> None:
        s = self.settings
        self.scheduler.add_job(
            self._run_prices,
            "interval",
            seconds=s.price_poll_seconds,
            id="prices",
            max_instances=1,
            coalesce=True,
            next_run_time=None,
        )
        self.scheduler.add_job(
            self._run_meter,
            "interval",
            seconds=s.meter_poll_seconds,
            id="meter",
            max_instances=1,
            coalesce=True,
            next_run_time=None,
        )
        self.scheduler.start()
        _LOG.info(
            "scheduler started (prices=%ds, meter=%ds, mock=%s)",
            s.price_poll_seconds,
            s.meter_poll_seconds,
            s.comet_mock,
        )
        # Kick off an immediate fill so the UI is not empty on first load.
        asyncio.create_task(self._bootstrap())

    async def _bootstrap(self) -> None:
        await ingest.startup_backfill(self.price_provider, self.meter_provider, self.settings.tz)
        await self._run_prices()
        await self._run_meter()

    async def _run_prices(self) -> None:
        try:
            await ingest.ingest_prices(self.price_provider)
        except Exception:  # noqa: BLE001
            _LOG.exception("price job error")

    async def _run_meter(self) -> None:
        try:
            await ingest.ingest_meter(self.meter_provider)
        except Exception:  # noqa: BLE001
            _LOG.exception("meter job error")

    async def stop(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
