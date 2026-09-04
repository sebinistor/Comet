"""Test config.

Environment is set here at import time — before any ``app.*`` module is imported —
so the SQLite engine is created against a throwaway directory and mock providers
are used (no credentials, no network).
"""

from __future__ import annotations

import os
import tempfile

_TMP = tempfile.mkdtemp(prefix="comet-test-")
os.environ.setdefault("COMET_MOCK", "1")
os.environ["COMET_DATA_DIR"] = _TMP
os.environ.setdefault("COMET_TZ", "America/Chicago")
os.environ.pop("EMPORIA_USERNAME", None)
os.environ.pop("EMPORIA_PASSWORD", None)

import pytest  # noqa: E402

from app.db import engine, init_db  # noqa: E402
from app.models import Base  # noqa: E402


@pytest.fixture()
def clean_db():
    Base.metadata.drop_all(engine)
    init_db()
    yield
