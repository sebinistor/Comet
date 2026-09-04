"""Poll providers and upsert samples into SQLite."""

from __future__ import annotations

import datetime as dt
import logging
from collections import defaultdict

from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.db import session_scope
from app.models import Consumption, Price, get_all_settings
from app.providers.base import MeterProvider, PriceProvider, PriceSample

_LOG = logging.getLogger("comet.ingest")
_UTC = dt.timezone.utc

# Surfaced by GET /api/health.
LAST_RUN: dict[str, dict] = {
    "prices": {"ok": None, "at": None, "detail": None},
    "meter": {"ok": None, "at": None, "detail": None},
    "backfill": {"ok": None, "at": None, "detail": None},
}


def _mark(job: str, ok: bool, detail: str) -> None:
    LAST_RUN[job] = {
        "ok": ok,
        "at": dt.datetime.now(tz=_UTC).isoformat(),
        "detail": detail,
    }


def _upsert_prices(rows: list[PriceSample]) -> int:
    if not rows:
        return 0
    payload = [
        {"ts_utc": r.ts_utc.astimezone(_UTC).replace(tzinfo=None), "kind": r.kind, "price_cents": r.price_cents}
        for r in rows
    ]
    stmt = sqlite_insert(Price).values(payload)
    stmt = stmt.on_conflict_do_update(
        index_elements=["ts_utc", "kind"],
        set_={"price_cents": stmt.excluded.price_cents},
    )
    with session_scope() as s:
        s.execute(stmt)
    return len(payload)


def _upsert_consumption(rows: list, resolution: str) -> int:
    if not rows:
        return 0
    payload = [
        {
            "ts_utc": r.ts_utc.astimezone(_UTC).replace(tzinfo=None),
            "device_gid": r.device_gid,
            "kwh": r.kwh,
            "resolution": resolution,
        }
        for r in rows
    ]
    stmt = sqlite_insert(Consumption).values(payload)
    stmt = stmt.on_conflict_do_update(
        index_elements=["ts_utc", "device_gid"],
        set_={"kwh": stmt.excluded.kwh, "resolution": stmt.excluded.resolution},
    )
    with session_scope() as s:
        s.execute(stmt)
    return len(payload)


def _derive_hourly(samples: list[PriceSample], *, only_complete: bool = True) -> list[PriceSample]:
    """Average 5-minute samples into hour_avg rows (for historical hours)."""
    buckets: dict[dt.datetime, list[float]] = defaultdict(list)
    for s in samples:
        hour = s.ts_utc.astimezone(_UTC).replace(minute=0, second=0, microsecond=0)
        buckets[hour].append(s.price_cents)
    now_hour = dt.datetime.now(tz=_UTC).replace(minute=0, second=0, microsecond=0)
    out: list[PriceSample] = []
    for hour, vals in buckets.items():
        if only_complete and hour >= now_hour:
            continue
        out.append(PriceSample(ts_utc=hour, price_cents=round(sum(vals) / len(vals), 4), kind="hour_avg"))
    return out


async def ingest_prices(provider: PriceProvider) -> dict:
    try:
        five = await provider.recent_five_minute()
        n_five = _upsert_prices(five)
        n_hour = _upsert_prices(_derive_hourly(five))
        try:
            cur = await provider.current_hour_average()
            n_hour += _upsert_prices([cur])
        except Exception as exc:  # noqa: BLE001
            _LOG.warning("currenthouraverage failed: %s", exc)
        detail = f"{n_five} 5-min, {n_hour} hourly"
        _mark("prices", True, detail)
        return {"five_minute": n_five, "hourly": n_hour}
    except Exception as exc:  # noqa: BLE001
        _LOG.exception("price ingest failed")
        _mark("prices", False, str(exc))
        raise


async def ingest_meter(provider: MeterProvider) -> dict:
    try:
        rows = await provider.latest_minute()
        n = _upsert_consumption(rows, "minute")
        _mark("meter", True, f"{n} minute samples")
        return {"minute_samples": n}
    except Exception as exc:  # noqa: BLE001
        _LOG.exception("meter ingest failed")
        _mark("meter", False, str(exc))
        raise


async def startup_backfill(price: PriceProvider, meter: MeterProvider, tz: dt.tzinfo) -> dict:
    """Seed price + consumption history so rollups are populated on first run."""
    try:
        now = dt.datetime.now(tz=_UTC)
        cfg = get_all_settings()
        cycle_start = dt.date.fromisoformat(str(cfg["billing_cycle_start"]))
        hist_start = dt.datetime(cycle_start.year, cycle_start.month, cycle_start.day, tzinfo=tz).astimezone(_UTC)
        # Cap backfill span so a stale cycle-start date can't trigger a huge pull.
        hist_start = max(hist_start, now - dt.timedelta(days=45))

        n_price = 0
        cursor = hist_start
        while cursor < now:
            chunk_end = min(cursor + dt.timedelta(hours=24), now)
            samples = await price.recent_five_minute(cursor, chunk_end)
            n_price += _upsert_prices(samples)
            n_price += _upsert_prices(_derive_hourly(samples))
            cursor = chunk_end

        hourly = await meter.backfill_hourly(hist_start, now - dt.timedelta(hours=1))
        n_meter = _upsert_consumption(hourly, "hour")

        detail = f"{n_price} price rows, {n_meter} hourly consumption rows since {hist_start.date()}"
        _mark("backfill", True, detail)
        _LOG.info("startup backfill: %s", detail)
        return {"price_rows": n_price, "consumption_rows": n_meter}
    except Exception as exc:  # noqa: BLE001
        _LOG.exception("startup backfill failed")
        _mark("backfill", False, str(exc))
        return {"error": str(exc)}
