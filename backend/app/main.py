"""FastAPI application entrypoint.

Serves the JSON API under ``/api`` and the built React SPA for everything else.
Background polling is started/stopped with the app lifespan.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.config import get_settings
from app.db import init_db
from app.routers.api import router as api_router
from app.scheduler import Poller

logging.basicConfig(
    level=os.environ.get("COMET_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
_LOG = logging.getLogger("comet")


def _static_dir() -> Path | None:
    candidates = [
        os.environ.get("COMET_STATIC_DIR"),
        "/app/static",
        str(Path(__file__).resolve().parents[2] / "frontend" / "dist"),
    ]
    for c in candidates:
        if c and Path(c).is_dir():
            return Path(c)
    return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    poller = Poller()
    app.state.poller = poller
    await poller.start()
    try:
        yield
    finally:
        await poller.stop()


app = FastAPI(title="Comet", version=__version__, lifespan=lifespan)
app.include_router(api_router)


@app.get("/api")
def api_index() -> JSONResponse:
    return JSONResponse(
        {
            "name": "comet",
            "version": __version__,
            "endpoints": ["/api/now", "/api/summary", "/api/history", "/api/config", "/api/health"],
        }
    )


_static = _static_dir()
if _static is not None:
    _LOG.info("serving frontend from %s", _static)
    app.mount("/assets", StaticFiles(directory=_static / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):  # noqa: ANN201
        target = _static / full_path
        if full_path and target.is_file():
            return FileResponse(target)
        return FileResponse(_static / "index.html")
else:
    _LOG.warning("no built frontend found; API only")

    @app.get("/")
    def root() -> JSONResponse:
        return JSONResponse({"name": "comet", "version": __version__, "frontend": "not built"})


def main() -> None:
    import uvicorn

    settings = get_settings()
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.comet_port, log_level="info")


if __name__ == "__main__":
    main()
