from __future__ import annotations

import datetime as dt

import pytest
from fastapi.testclient import TestClient

from app.db import session_scope
from app.main import app
from app.models import Consumption, Price
from app.services import ingest
from app.providers.mock import MockMeterProvider, MockPriceProvider

_UTC = dt.timezone.utc


@pytest.fixture()
def client(clean_db):
    with TestClient(app) as c:  # runs lifespan (scheduler + bootstrap on mock data)
        yield c


def test_health_reports_mock_and_scheduler(client):
    body = client.get("/api/health").json()
    assert body["mock"] is True
    assert body["scheduler_running"] is True
    assert set(body["jobs"]) == {"prices", "meter", "backfill"}


def test_now_has_price_and_power_after_bootstrap(client):
    body = client.get("/api/now").json()
    assert body["price_cents_per_kwh"] is not None
    assert body["power_watts"] is not None
    assert body["cost_rate_per_hour"] is not None


def test_summary_shape_and_nonnegative(client):
    body = client.get("/api/summary").json()
    assert body["cost_mode"] in {"supply", "total"}
    for block in ("day", "invoice"):
        assert body[block]["kwh"] >= 0
        assert body[block]["supply_cost"] >= 0
    assert "projected_total_cost" in body["invoice"]


def test_config_round_trip(client):
    client.put("/api/config", json={"cost_mode": "total", "delivery_cents_per_kwh": 4.5})
    cfg = client.get("/api/config").json()
    assert cfg["cost_mode"] == "total"
    assert cfg["delivery_cents_per_kwh"] == 4.5


def test_history_day_returns_hourly_points(client):
    body = client.get("/api/history?range=day").json()
    assert body["range"] == "day"
    assert isinstance(body["points"], list)
    if body["points"]:
        p = body["points"][0]
        assert {"ts", "price_cents", "kwh", "cost", "cumulative_cost"} <= set(p)


@pytest.mark.asyncio
async def test_ingest_prices_and_meter_populate_db(clean_db):
    await ingest.ingest_prices(MockPriceProvider())
    await ingest.ingest_meter(MockMeterProvider())
    with session_scope() as s:
        assert s.query(Price).filter_by(kind="5min").count() > 0
        assert s.query(Consumption).count() >= 1
