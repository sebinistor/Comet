"""Emporia Vue consumption via the community ``pyemvue`` cloud library.

Emporia exposes no local device API, so everything here goes through the Emporia
cloud. ``pyemvue`` is synchronous; calls are pushed to a worker thread.

Login persists tokens to ``settings.emporia_token_file`` on the mounted volume and
``pyemvue`` refreshes them in place, so a password is only needed on first run.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import logging

from app.config import Settings
from app.providers.base import ConsumptionSample, MeterProvider

_LOG = logging.getLogger("comet.emporia")

# Emporia reports the whole-home mains as this synthetic channel number.
MAINS_CHANNEL = "1,2,3"


class EmporiaMeterProvider(MeterProvider):
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._vue = None
        self._gids: list[int] = list(settings.device_gid_list)
        self._lock = asyncio.Lock()

    # --- connection ----------------------------------------------------------
    def _connect_sync(self):
        from pyemvue import PyEmVue

        vue = PyEmVue()
        token_file = str(self._settings.emporia_token_file)
        if self._settings.emporia_token_file.exists():
            try:
                vue.login(token_storage_file=token_file)
                _LOG.info("emporia: authenticated from saved tokens")
                return vue
            except Exception as exc:  # noqa: BLE001
                _LOG.warning("emporia: saved token login failed (%s), retrying with password", exc)
        vue.login(
            username=self._settings.emporia_username,
            password=self._settings.emporia_password,
            token_storage_file=token_file,
        )
        _LOG.info("emporia: authenticated with username/password")
        return vue

    async def _vue_client(self):
        async with self._lock:
            if self._vue is None:
                self._vue = await asyncio.to_thread(self._connect_sync)
                if not self._gids:
                    devices = await asyncio.to_thread(self._vue.get_devices)
                    self._gids = [d.device_gid for d in devices]
                    _LOG.info("emporia: tracking device gids %s", self._gids)
            return self._vue

    # --- reads -------------------------------------------------------------------
    def _list_usage_sync(self, scale: str, unit: str, instant: dt.datetime | None):
        from pyemvue.enums import Scale, Unit  # noqa: F401  (kept for reference)

        return self._vue.get_device_list_usage(
            deviceGids=self._gids,
            instant=instant,
            scale=scale,
            unit=unit,
        )

    @staticmethod
    def _pick_channel(device_usage):
        channels = getattr(device_usage, "channels", {}) or {}
        if MAINS_CHANNEL in channels:
            return channels[MAINS_CHANNEL]
        # Fall back to the sum of all channels on the device.
        total = 0.0
        found = False
        for ch in channels.values():
            usage = getattr(ch, "usage", None)
            if usage is not None:
                total += usage
                found = True
        if not found:
            return None

        class _Synthetic:
            pass

        s = _Synthetic()
        s.usage = total
        return s

    async def latest_minute(self) -> list[ConsumptionSample]:
        from pyemvue.enums import Scale, Unit

        vue = await self._vue_client()
        ts = dt.datetime.now(tz=dt.timezone.utc).replace(second=0, microsecond=0) - dt.timedelta(minutes=1)
        usage = await asyncio.to_thread(
            vue.get_device_list_usage, self._gids, ts, Scale.MINUTE.value, Unit.KWH.value
        )
        out: list[ConsumptionSample] = []
        for gid, dev in (usage or {}).items():
            ch = self._pick_channel(dev)
            if ch is None or ch.usage is None:
                continue
            out.append(ConsumptionSample(ts_utc=ts, device_gid=str(gid), kwh=max(ch.usage, 0.0)))
        return out

    async def instant_watts(self) -> float:
        from pyemvue.enums import Scale, Unit

        vue = await self._vue_client()
        usage = await asyncio.to_thread(
            vue.get_device_list_usage, self._gids, None, Scale.MINUTE.value, Unit.KWH.value
        )
        watts = 0.0
        for dev in (usage or {}).values():
            ch = self._pick_channel(dev)
            if ch is not None and ch.usage is not None:
                # kWh accrued so far this minute -> average kW -> W. Coarse but adequate
                # for a live readout; a fresh sample lands every poll interval.
                watts += max(ch.usage, 0.0) * 60_000.0
        return watts

    async def backfill_hourly(
        self, start: dt.datetime, end: dt.datetime
    ) -> list[ConsumptionSample]:
        from pyemvue.enums import Scale, Unit

        vue = await self._vue_client()
        devices = await asyncio.to_thread(vue.get_devices)
        wanted = {int(g) for g in self._gids}
        out: list[ConsumptionSample] = []
        for device in devices:
            if device.device_gid not in wanted:
                continue
            for channel in device.channels:
                if channel.channel_num != MAINS_CHANNEL:
                    continue
                try:
                    values, start_time = await asyncio.to_thread(
                        vue.get_chart_usage,
                        channel,
                        start,
                        end,
                        Scale.HOUR.value,
                        Unit.KWH.value,
                    )
                except Exception as exc:  # noqa: BLE001
                    _LOG.warning("emporia backfill failed for gid %s: %s", device.device_gid, exc)
                    continue
                cursor = start_time
                for v in values:
                    if v is not None:
                        out.append(
                            ConsumptionSample(
                                ts_utc=cursor.astimezone(dt.timezone.utc),
                                device_gid=str(device.device_gid),
                                kwh=max(v, 0.0),
                            )
                        )
                    cursor += dt.timedelta(hours=1)
        _LOG.info("emporia backfill: %d hourly samples", len(out))
        return out
