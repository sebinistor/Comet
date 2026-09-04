"""Data-source providers (ComEd prices, Emporia consumption) behind small ABCs."""

from __future__ import annotations

from app.config import Settings, get_settings
from app.providers.base import MeterProvider, PriceProvider


def build_providers(settings: Settings | None = None) -> tuple[PriceProvider, MeterProvider]:
    settings = settings or get_settings()
    if settings.comet_mock:
        from app.providers.mock import MockMeterProvider, MockPriceProvider

        return MockPriceProvider(), MockMeterProvider()

    from app.providers.comed import ComEdPriceProvider
    from app.providers.emporia import EmporiaMeterProvider

    return ComEdPriceProvider(), EmporiaMeterProvider(settings)


__all__ = ["MeterProvider", "PriceProvider", "build_providers"]
