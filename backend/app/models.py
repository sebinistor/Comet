"""ORM models and the user-editable settings store.

Tables
------
``prices``       — ComEd price samples. ``kind`` is ``"5min"`` (real-time market
                   price, used for the live tile/chart) or ``"hour_avg"`` (the
                   hour's billed-basis average, used for cost rollups).
``consumption``  — per-minute kWh per Emporia device channel (GID).
``settings``     — JSON-valued key/value rows edited from the UI.
"""

from __future__ import annotations

import datetime as dt
import json
from typing import Any

from sqlalchemy import Float, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.db import SessionLocal


class Base(DeclarativeBase):
    pass


class Price(Base):
    __tablename__ = "prices"
    __table_args__ = (UniqueConstraint("ts_utc", "kind", name="uq_price_ts_kind"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_utc: Mapped[dt.datetime] = mapped_column(index=True)
    kind: Mapped[str] = mapped_column(String(16))
    price_cents: Mapped[float] = mapped_column(Float)


class Consumption(Base):
    __tablename__ = "consumption"
    __table_args__ = (
        UniqueConstraint("ts_utc", "device_gid", name="uq_consumption_ts_gid"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts_utc: Mapped[dt.datetime] = mapped_column(index=True)
    device_gid: Mapped[str] = mapped_column(String(64), default="total")
    kwh: Mapped[float] = mapped_column(Float)
    # "minute" (live polling) or "hour" (historical backfill). Lets rollups avoid
    # double-counting an hour that has both, and lets the chart pick a grain.
    resolution: Mapped[str] = mapped_column(String(8), default="minute")


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value_json: Mapped[str] = mapped_column(String)


# --- Settings helpers --------------------------------------------------------

DEFAULT_SETTINGS: dict[str, Any] = {
    # ISO date the current invoice period began (meter-read day).
    "billing_cycle_start": (dt.date.today().replace(day=1)).isoformat(),
    # Nominal length of a billing cycle, used for projection.
    "billing_cycle_days": 30,
    # Adders used only when cost_mode == "total".
    "delivery_cents_per_kwh": 0.0,
    "other_cents_per_kwh": 0.0,
    "fixed_monthly_charge": 0.0,
    "tax_rate_pct": 0.0,
    # "supply" (ComEd hourly price only) or "total" (approximate full bill).
    "cost_mode": "supply",
}


def seed_default_settings() -> None:
    with SessionLocal() as session:
        existing = {s.key for s in session.query(Setting).all()}
        for key, value in DEFAULT_SETTINGS.items():
            if key not in existing:
                session.add(Setting(key=key, value_json=json.dumps(value)))
        session.commit()


def get_all_settings() -> dict[str, Any]:
    merged = dict(DEFAULT_SETTINGS)
    with SessionLocal() as session:
        for row in session.query(Setting).all():
            try:
                merged[row.key] = json.loads(row.value_json)
            except json.JSONDecodeError:
                merged[row.key] = row.value_json
    return merged


def update_settings(values: dict[str, Any]) -> dict[str, Any]:
    with SessionLocal() as session:
        for key, value in values.items():
            if key not in DEFAULT_SETTINGS:
                continue
            row = session.get(Setting, key)
            if row is None:
                session.add(Setting(key=key, value_json=json.dumps(value)))
            else:
                row.value_json = json.dumps(value)
        session.commit()
    return get_all_settings()
