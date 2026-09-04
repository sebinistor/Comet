"""Cost roll-up math.

The billed supply charge under ComEd Hourly Pricing is the hourly price applied
to each hour's usage, so rollups price every consumption sample at the average
price of the hour it falls in (``hour_avg`` rows), falling back to the nearest
5-minute price, then to a caller-supplied default.

``total`` mode approximates the full bill by adding user-configured
delivery / rider / fixed / tax components on top of the supply charge. It is an
estimate, not a guaranteed match to the printed invoice.
"""

from __future__ import annotations

import bisect
import datetime as dt
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Consumption, Price, get_all_settings

_UTC = dt.timezone.utc


def _floor_hour(ts: dt.datetime) -> dt.datetime:
    return ts.astimezone(_UTC).replace(minute=0, second=0, microsecond=0)


@dataclass(slots=True)
class Rollup:
    kwh: float
    supply_cost: float
    total_cost: float
    start: dt.datetime
    end: dt.datetime


class PriceLookup:
    """Resolve a price (cents/kWh) for an arbitrary timestamp."""

    def __init__(self, session: Session, start: dt.datetime, end: dt.datetime, default_cents: float):
        self.default_cents = default_cents
        pad = dt.timedelta(hours=1)
        rows = session.execute(
            select(Price).where(Price.ts_utc >= start - pad, Price.ts_utc <= end + pad)
        ).scalars().all()
        self._hour: dict[dt.datetime, float] = {}
        self._five_ts: list[dt.datetime] = []
        self._five_val: list[float] = []
        for r in sorted(rows, key=lambda x: x.ts_utc):
            ts = r.ts_utc if r.ts_utc.tzinfo else r.ts_utc.replace(tzinfo=_UTC)
            if r.kind == "hour_avg":
                self._hour[_floor_hour(ts)] = r.price_cents
            else:
                self._five_ts.append(ts)
                self._five_val.append(r.price_cents)

    def cents(self, ts: dt.datetime) -> float:
        ts = ts.astimezone(_UTC)
        hourly = self._hour.get(_floor_hour(ts))
        if hourly is not None:
            return hourly
        if self._five_ts:
            i = bisect.bisect_left(self._five_ts, ts)
            candidates = []
            if i < len(self._five_ts):
                candidates.append(i)
            if i > 0:
                candidates.append(i - 1)
            best = min(candidates, key=lambda j: abs(self._five_ts[j] - ts))
            if abs(self._five_ts[best] - ts) <= dt.timedelta(minutes=30):
                return self._five_val[best]
        return self.default_cents


def compute_rollup(
    session: Session,
    start: dt.datetime,
    end: dt.datetime,
    *,
    settings: dict | None = None,
    default_price_cents: float = 0.0,
) -> Rollup:
    cfg = settings or get_all_settings()
    start = start.astimezone(_UTC)
    end = end.astimezone(_UTC)

    rows = session.execute(
        select(Consumption)
        .where(Consumption.ts_utc >= start, Consumption.ts_utc < end)
        .order_by(Consumption.ts_utc)
    ).scalars().all()

    # If an hour has minute-resolution samples, drop the hour-resolution row for
    # that same hour to avoid double counting.
    minute_hours = {
        _floor_hour(r.ts_utc if r.ts_utc.tzinfo else r.ts_utc.replace(tzinfo=_UTC))
        for r in rows
        if r.resolution == "minute"
    }

    lookup = PriceLookup(session, start, end, default_price_cents)

    kwh = 0.0
    supply_cost = 0.0
    for r in rows:
        ts = r.ts_utc if r.ts_utc.tzinfo else r.ts_utc.replace(tzinfo=_UTC)
        if r.resolution == "hour" and _floor_hour(ts) in minute_hours:
            continue
        kwh += r.kwh
        supply_cost += r.kwh * lookup.cents(ts) / 100.0

    total_cost = supply_cost
    if cfg.get("cost_mode") == "total":
        total_cost += kwh * float(cfg.get("delivery_cents_per_kwh", 0.0)) / 100.0
        total_cost += kwh * float(cfg.get("other_cents_per_kwh", 0.0)) / 100.0
        total_cost += float(cfg.get("fixed_monthly_charge", 0.0))
        total_cost *= 1.0 + float(cfg.get("tax_rate_pct", 0.0)) / 100.0

    return Rollup(
        kwh=round(kwh, 4),
        supply_cost=round(supply_cost, 4),
        total_cost=round(total_cost, 4),
        start=start,
        end=end,
    )


def _cycle_start_dt(cfg: dict, tz: dt.tzinfo) -> dt.datetime:
    d = dt.date.fromisoformat(str(cfg["billing_cycle_start"]))
    return dt.datetime(d.year, d.month, d.day, tzinfo=tz)


def build_summary(session: Session, tz: dt.tzinfo, *, default_price_cents: float = 0.0) -> dict:
    cfg = get_all_settings()
    now = dt.datetime.now(tz=tz)

    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    day = compute_rollup(
        session, midnight, now, settings=cfg, default_price_cents=default_price_cents
    )

    cycle_start = _cycle_start_dt(cfg, tz)
    invoice = compute_rollup(
        session, cycle_start, now, settings=cfg, default_price_cents=default_price_cents
    )

    cycle_days = float(cfg.get("billing_cycle_days", 30))
    elapsed = max((now - cycle_start).total_seconds() / 86400.0, 1e-6)
    scale = cycle_days / elapsed if elapsed < cycle_days else 1.0
    projected_supply = round(invoice.supply_cost * scale, 2)
    projected_total = round(invoice.total_cost * scale, 2)

    return {
        "cost_mode": cfg.get("cost_mode", "supply"),
        "generated_at": now.astimezone(_UTC).isoformat(),
        "day": {
            "kwh": day.kwh,
            "supply_cost": round(day.supply_cost, 2),
            "total_cost": round(day.total_cost, 2),
            "start": day.start.isoformat(),
        },
        "invoice": {
            "kwh": invoice.kwh,
            "supply_cost": round(invoice.supply_cost, 2),
            "total_cost": round(invoice.total_cost, 2),
            "cycle_start": cycle_start.date().isoformat(),
            "days_elapsed": round(elapsed, 2),
            "days_in_cycle": cycle_days,
            "projected_supply_cost": projected_supply,
            "projected_total_cost": projected_total,
        },
    }
