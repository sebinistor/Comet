from __future__ import annotations

import datetime as dt

from app.providers.comed import _parse_feed


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
