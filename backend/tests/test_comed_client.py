from __future__ import annotations

import datetime as dt

import pytest

from app.providers.comed import ComEdPriceProvider, _parse_feed


def test_parse_feed_sorts_and_converts_millis():
    payload = [
        {"millisUTC": "1434686700000", "price": "2.0"},
        {"millisUTC": "1434686100000", "price": "2.5"},
        {"millisUTC": "bad", "price": "9"},
        {"price": "no-ts"},
    ]
    out = _parse_feed(payload, "5min")
    assert [s.price_cents for s in out] == [2.5, 2.0]
    assert out[0].ts_utc < out[1].ts_utc
    assert out[0].ts_utc.tzinfo == dt.timezone.utc
    assert all(s.kind == "5min" for s in out)


def test_parse_feed_handles_empty():
    assert _parse_feed([], "hour_avg") == []


class _CapturingClient:
    """Minimal stand-in for httpx.AsyncClient that records the last request."""

    def __init__(self) -> None:
        self.params: dict | None = None

    async def get(self, url, params=None):  # noqa: ANN001
        self.params = params

        class _Resp:
            def raise_for_status(self) -> None:
                pass

            def json(self):  # noqa: ANN201
                return []

        return _Resp()


@pytest.mark.asyncio
async def test_recent_five_minute_formats_bounds_in_central_time():
    client = _CapturingClient()
    provider = ComEdPriceProvider(client=client)
    # 2026-08-20 00:00 UTC is 2026-08-19 19:00 in Central (CDT, UTC-5).
    start = dt.datetime(2026, 8, 20, 0, 0, tzinfo=dt.timezone.utc)
    end = dt.datetime(2026, 8, 21, 0, 0, tzinfo=dt.timezone.utc)
    await provider.recent_five_minute(start, end)
    assert client.params["datestart"] == "202608191900"
    assert client.params["dateend"] == "202608201900"
