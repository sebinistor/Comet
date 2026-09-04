"""Pydantic response / request models for the HTTP API."""

from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field


class NowResponse(BaseModel):
    generated_at: dt.datetime
    price_cents_per_kwh: float | None
    price_ts: dt.datetime | None
    hour_avg_cents_per_kwh: float | None
    power_watts: float | None
    cost_rate_per_hour: float | None  # $/hr at current price and draw


class RollupBlock(BaseModel):
    kwh: float
    supply_cost: float
    total_cost: float


class InvoiceBlock(RollupBlock):
    cycle_start: dt.date
    days_elapsed: float
    days_in_cycle: float
    projected_supply_cost: float
    projected_total_cost: float


class SummaryResponse(BaseModel):
    cost_mode: Literal["supply", "total"]
    generated_at: dt.datetime
    day: dict
    invoice: dict


class HistoryPoint(BaseModel):
    ts: dt.datetime
    price_cents: float | None = None
    kwh: float | None = None
    cost: float | None = None
    cumulative_cost: float | None = None


class HistoryResponse(BaseModel):
    range: str
    start: dt.datetime
    end: dt.datetime
    points: list[HistoryPoint]


class ConfigModel(BaseModel):
    billing_cycle_start: dt.date
    billing_cycle_days: int = Field(ge=1, le=90)
    delivery_cents_per_kwh: float = Field(ge=0)
    other_cents_per_kwh: float = Field(ge=0)
    fixed_monthly_charge: float = Field(ge=0)
    tax_rate_pct: float = Field(ge=0, le=100)
    cost_mode: Literal["supply", "total"]


class ConfigUpdate(BaseModel):
    billing_cycle_start: dt.date | None = None
    billing_cycle_days: int | None = Field(default=None, ge=1, le=90)
    delivery_cents_per_kwh: float | None = Field(default=None, ge=0)
    other_cents_per_kwh: float | None = Field(default=None, ge=0)
    fixed_monthly_charge: float | None = Field(default=None, ge=0)
    tax_rate_pct: float | None = Field(default=None, ge=0, le=100)
    cost_mode: Literal["supply", "total"] | None = None


class HealthJob(BaseModel):
    ok: bool | None
    at: dt.datetime | None
    detail: str | None


class HealthResponse(BaseModel):
    status: str
    mock: bool
    scheduler_running: bool
    jobs: dict[str, HealthJob]
