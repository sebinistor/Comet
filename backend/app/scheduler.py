"""Background polling via APScheduler, running in the FastAPI event loop."""

from __future__ import annotations

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import get_settings
from app.providers import build_providers
from app.services import costing, ingest

_LOG = logging.getLogger("comet.scheduler")


class Poller:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.price_provider, self.meter_provider = build_providers(self.settings)
        self.scheduler = AsyncIOScheduler(timezone="UTC")

    async def start(self) -> None:
        s = self.settings
        # NB: do not pass ``next_run_time=None`` here -- APScheduler reads that as
        # "add the job paused", so the interval never fires and the only data we
        # ever get is the one-shot ``_bootstrap`` below. Omitting it lets the
        # trigger schedule the first run at now + interval.
        self.scheduler.add_job(
            self._run_prices,
            "interval",
            seconds=s.price_poll_seconds,
            id="prices",
            max_instances=1,
            coalesce=True,
        )
        self.scheduler.add_job(
            self._run_meter,
            "interval",
            seconds=s.meter_poll_seconds,
            id="meter",
            max_instances=1,
            coalesce=True,
        )
        # Cheap date check, not data volume -- hourly is plenty often to catch
        # a cycle rollover the same day it happens.
        self.scheduler.add_job(
            self._run_cycle_check,
            "interval",
            seconds=3600,
            id="cycle",
            max_instances=1,
            coalesce=True,
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
        # Catch up immediately on restart if a cycle boundary was crossed while
        # the app was down, rather than waiting up to an hour for the interval job.
        await self._run_cycle_check()

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

    async def _run_cycle_check(self) -> None:
        try:
            closed = costing.close_due_cycles(self.settings.tz)
            if closed:
                _LOG.info(
                    "auto-closed billing cycle(s): %s",
                    [c["cycle_start"].isoformat() for c in closed],
                )
        except Exception:  # noqa: BLE001
            _LOG.exception("cycle check error")

    async def stop(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
