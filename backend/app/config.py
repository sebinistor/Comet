"""Process configuration.

Two layers:

* :class:`Settings` — immutable, read from environment / ``.env`` at startup
  (credentials, poll intervals, paths). These never change while running.
* The ``settings`` DB table — user-editable values changed from the UI
  (billing cycle start, delivery/tax adders, cost mode). Managed in
  :mod:`app.services.costing` / :mod:`app.routers.api`, not here.
"""

from __future__ import annotations

import functools
from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Emporia cloud credentials -------------------------------------------------
    emporia_username: str = ""
    emporia_password: str = ""
    # Comma-separated device GIDs to record. Empty => all devices on the account.
    emporia_device_gids: str = ""

    # --- Runtime ----------------------------------------------------------------
    comet_tz: str = "America/Chicago"
    comet_data_dir: Path = Path("/data")
    comet_port: int = 8080
    # When true, use deterministic fake providers and skip all cloud calls.
    comet_mock: bool = False

    # --- Poll intervals (seconds) --------------------------------------------------
    price_poll_seconds: int = 300
    meter_poll_seconds: int = 60

    # --- Derived helpers --------------------------------------------------------
    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.comet_tz)

    @property
    def db_path(self) -> Path:
        return self.comet_data_dir / "comet.db"

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.db_path}"

    @property
    def emporia_token_file(self) -> Path:
        return self.comet_data_dir / "emporia_tokens.json"

    @property
    def device_gid_list(self) -> list[int]:
        return [int(g) for g in self.emporia_device_gids.replace(" ", "").split(",") if g]


@functools.lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.comet_data_dir.mkdir(parents=True, exist_ok=True)
    return s
