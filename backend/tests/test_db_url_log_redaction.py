from __future__ import annotations

import pytest

from app.db import database


def test_safe_database_url_hides_the_password(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://postgres:s3cret-pw@db.internal:5432/railway")
    monkeypatch.setattr(database, "_database_url", None)

    safe = database.get_safe_database_url()

    assert "s3cret-pw" not in safe
