"""HTTP API: /api/now, /api/summary, /api/history, /api/config, /api/health."""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_session
from app.models import Consumption, Price, get_all_settings, update_settings
from app.schemas import (
    ConfigModel,
    ConfigUpdate,
    HealthResponse,
    HistoryResponse,
    NowResponse,
    SummaryResponse,
)
from app.services import ingest
from app.services.costing import PriceLookup, build_summary

router = APIRouter(prefix="/api")
_UTC = dt.timezone.utc


def _aware(ts: dt.datetime) -> dt.datetime:
    return ts if ts.tzinfo else ts.replace(tzinfo=_UTC)


def _latest_price(session: Session, kind: str) -> Price | None:
    return session.execute(
        select(Price).where(Price.kind == kind).order_by(Price.ts_utc.desc()).limit(1)
    ).scalars().first()


def _fallback_cents(session: Session) -> float:
    row = _latest_price(session, "hour_avg") or _latest_price(session, "5min")
    return row.price_cents if row else 0.0


@router.get("/now", response_model=NowResponse)
async def now(request: Request, session: Session = Depends(get_session)) -> NowResponse:
    five = _latest_price(session, "5min")
    hour_avg = _latest_price(session, "hour_avg")

    watts: float | None = None
    poller = getattr(request.app.state, "poller", None)
    if poller is not None:
        try:
            watts = await poller.meter_provider.instant_watts()
        except Exception:  # noqa: BLE001
            watts = None

    price_cents = five.price_cents if five else None
    cost_rate = None
    if price_cents is not None and watts is not None:
        cost_rate = round(watts / 1000.0 * price_cents / 100.0, 4)

    return NowResponse(
        generated_at=dt.datetime.now(tz=_UTC),
        price_cents_per_kwh=price_cents,
        price_ts=_aware(five.ts_utc) if five else None,
        hour_avg_cents_per_kwh=hour_avg.price_cents if hour_avg else None,
        power_watts=round(watts, 1) if watts is not None else None,
        cost_rate_per_hour=cost_rate,
    )


@router.get("/summary", response_model=SummaryResponse)
def summary(session: Session = Depends(get_session)) -> SummaryResponse:
    settings = get_settings()
    data = build_summary(session, settings.tz, default_price_cents=_fallback_cents(session))
    return SummaryResponse(**data)


@router.get("/history", response_model=HistoryResponse)
def history(
    range: str = Query("day", pattern="^(day|cycle)$"),
    session: Session = Depends(get_session),
) -> HistoryResponse:
    settings = get_settings()
    cfg = get_all_settings()
    now_local = dt.datetime.now(tz=settings.tz)

    if range == "day":
        start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        d = dt.date.fromisoformat(str(cfg["billing_cycle_start"]))
        start_local = dt.datetime(d.year, d.month, d.day, tzinfo=settings.tz)

    start = start_local.astimezone(_UTC)
    end = now_local.astimezone(_UTC)

    cons = session.execute(
        select(Consumption)
        .where(Consumption.ts_utc >= start.replace(tzinfo=None), Consumption.ts_utc < end.replace(tzinfo=None))
        .order_by(Consumption.ts_utc)
    ).scalars().all()

    minute_hours = {
        _aware(r.ts_utc).replace(minute=0, second=0, microsecond=0)
        for r in cons
        if r.resolution == "minute"
    }
    hourly_kwh: dict[dt.datetime, float] = {}
    for r in cons:
        hb = _aware(r.ts_utc).replace(minute=0, second=0, microsecond=0)
        if r.resolution == "hour" and hb in minute_hours:
            continue
        hourly_kwh[hb] = hourly_kwh.get(hb, 0.0) + r.kwh

    lookup = PriceLookup(session, start, end, _fallback_cents(session))
    delivery = float(cfg.get("delivery_cents_per_kwh", 0.0)) + float(cfg.get("other_cents_per_kwh", 0.0))
    total_mode = cfg.get("cost_mode") == "total"

    points = []
    cumulative = 0.0
    cursor = start.replace(minute=0, second=0, microsecond=0)
    while cursor < end:
        kwh = round(hourly_kwh.get(cursor, 0.0), 4)
        price_cents = round(lookup.cents(cursor), 3)
        cost = kwh * price_cents / 100.0
        if total_mode:
            cost += kwh * delivery / 100.0
        cumulative += cost
        points.append(
            {
                "ts": cursor,
                "price_cents": price_cents,
                "kwh": kwh,
                "cost": round(cost, 4),
                "cumulative_cost": round(cumulative, 4),
            }
        )
        cursor += dt.timedelta(hours=1)

    return HistoryResponse(range=range, start=start, end=end, points=points)


@router.get("/config", response_model=ConfigModel)
def get_config() -> ConfigModel:
    return ConfigModel(**get_all_settings())


@router.put("/config", response_model=ConfigModel)
def put_config(update: ConfigUpdate) -> ConfigModel:
    values = {k: v for k, v in update.model_dump().items() if v is not None}
    if isinstance(values.get("billing_cycle_start"), dt.date):
        values["billing_cycle_start"] = values["billing_cycle_start"].isoformat()
    merged = update_settings(values)
    return ConfigModel(**merged)


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    settings = get_settings()
    poller = getattr(request.app.state, "poller", None)
    running = bool(poller and poller.scheduler.running)
    jobs = ingest.LAST_RUN
    status = "ok"
    if any(j.get("ok") is False for j in jobs.values()):
        status = "degraded"
    return HealthResponse(
        status=status,
        mock=settings.comet_mock,
        scheduler_running=running,
        jobs=jobs,
    )
