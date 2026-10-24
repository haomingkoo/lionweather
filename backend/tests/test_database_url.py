from __future__ import annotations

import pytest

from app.db import database


@pytest.mark.parametrize("raw", ["postgres://u:p@h:5432/d", "postgresql://u:p@h:5432/d"])
def test_database_url_pins_psycopg2_driver(monkeypatch: pytest.MonkeyPatch, raw: str) -> None:
    monkeypatch.setenv("DATABASE_URL", raw)
    monkeypatch.setattr(database, "_database_url", None)

    url = database.get_database_url()

    assert url.startswith("postgresql+psycopg2://")
