from __future__ import annotations

import datetime as dt

import pytest

from app.db import session_scope
from app.models import Consumption, Price, update_settings
from app.services.costing import compute_rollup

_UTC = dt.timezone.utc


def _seed_flat(price_cents: float, kwh_per_hour: float, hours: int, start: dt.datetime):
    with session_scope() as s:
        for h in range(hours):
            ts = start + dt.timedelta(hours=h)
            s.add(Price(ts_utc=ts, kind="hour_avg", price_cents=price_cents))
            s.add(Consumption(ts_utc=ts, device_gid="x", kwh=kwh_per_hour, resolution="hour"))


@pytest.mark.usefixtures("clean_db")
def test_supply_rollup_is_kwh_times_price():
    start = dt.datetime(2026, 9, 1, 0, 0, tzinfo=_UTC)
    _seed_flat(price_cents=10.0, kwh_per_hour=2.0, hours=24, start=start)

    r = compute_rollup(_session(), start, start + dt.timedelta(hours=24))
    assert r.kwh == pytest.approx(48.0)
    # 48 kWh * 10 c/kWh = 480 c = $4.80
    assert r.supply_cost == pytest.approx(4.80)
    assert r.total_cost == pytest.approx(4.80)  # supply mode by default


@pytest.mark.usefixtures("clean_db")
def test_total_mode_adds_delivery_fixed_and_tax():
    start = dt.datetime(2026, 9, 1, 0, 0, tzinfo=_UTC)
    _seed_flat(price_cents=10.0, kwh_per_hour=1.0, hours=10, start=start)
    update_settings(
        {
            "cost_mode": "total",
            "delivery_cents_per_kwh": 5.0,
            "other_cents_per_kwh": 1.0,
            "fixed_monthly_charge": 12.0,
            "tax_rate_pct": 10.0,
        }
    )

    r = compute_rollup(_session(), start, start + dt.timedelta(hours=10))
    # 10 kWh. supply = 10 * 0.10 = 1.00
    # delivery+other = 10 * 0.06 = 0.60 ; fixed = 12.00
    # subtotal = 13.60 ; *1.10 tax = 14.96
    assert r.supply_cost == pytest.approx(1.00)
    assert r.total_cost == pytest.approx(14.96)


@pytest.mark.usefixtures("clean_db")
def test_minute_rows_override_hour_rows_for_same_hour():
    start = dt.datetime(2026, 9, 1, 0, 0, tzinfo=_UTC)
    with session_scope() as s:
        s.add(Price(ts_utc=start, kind="hour_avg", price_cents=10.0))
        # A stale hourly backfill row for this hour...
        s.add(Consumption(ts_utc=start, device_gid="backfill", kwh=5.0, resolution="hour"))
        # ...superseded by 60 minute-resolution samples.
        for m in range(60):
            s.add(
                Consumption(
                    ts_utc=start + dt.timedelta(minutes=m),
                    device_gid="x",
                    kwh=0.01,
                    resolution="minute",
                )
            )
    r = compute_rollup(_session(), start, start + dt.timedelta(hours=1))
    # hour row (5.0) is dropped; only the 60 * 0.01 = 0.6 kWh minute rows count
    assert r.kwh == pytest.approx(0.6)
    assert r.supply_cost == pytest.approx(0.6 * 10.0 / 100.0)


@pytest.mark.usefixtures("clean_db")
def test_default_price_used_when_no_price_rows():
    start = dt.datetime(2026, 9, 1, 0, 0, tzinfo=_UTC)
    with session_scope() as s:
        s.add(Consumption(ts_utc=start, device_gid="x", kwh=3.0, resolution="hour"))
    r = compute_rollup(_session(), start, start + dt.timedelta(hours=1), default_price_cents=8.0)
    assert r.supply_cost == pytest.approx(3.0 * 8.0 / 100.0)


def _session():
    from app.db import SessionLocal

    return SessionLocal()
