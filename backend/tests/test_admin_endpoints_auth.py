from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db import database
from app.db.migrations import migrate_forecast_tables
from app.routers import forecasts, ml, ml_forecast, ml_models, ml_predictions, performance


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("ADMIN_SECRET", "s3cret")
    app = FastAPI()
    app.include_router(performance.router, prefix="/api")
    app.include_router(ml_forecast.router, prefix="/api")
    app.include_router(ml.router)
    app.include_router(ml_predictions.router)
    app.include_router(ml_models.router)
    app.include_router(forecasts.router, prefix="/api")
    return TestClient(app)


@pytest.mark.parametrize(
    "path",
    [
        "/api/performance/record-prediction",
        "/api/performance/record-actual",
        "/api/ml/versions/v1/activate?model_name=m",
        "/api/ml-predictions/predict",
        "/api/ml-predictions/predict-all",
    ],
)
@pytest.mark.parametrize("headers", [{}, {"X-Admin-Secret": "nope"}])
def test_state_changing_post_without_valid_secret_is_forbidden(client, path, headers):
    response = client.post(path, json={}, headers=headers)

    assert response.status_code == 403


@pytest.mark.parametrize("path", ["/api/ml/training/trigger", "/api/ml/record-actual"])
def test_removed_stub_routes_are_gone(client, path):
    response = client.post(path, json={})

    assert response.status_code in (404, 405)


def test_activate_with_secret_reaches_handler(client, monkeypatch):
    monkeypatch.setattr(ml_models, "fetch_one", lambda *a, **k: None)

    response = client.post(
        "/api/ml/versions/v1/activate?model_name=m", headers={"X-Admin-Secret": "s3cret"}
    )

    assert response.status_code == 404


def test_forecast_compare_returns_recent_rows(client, monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setattr(database, "_database_url", None)
    monkeypatch.setattr(database, "_engine", None)
    migrate_forecast_tables()
    now = datetime.now(timezone.utc)
    for ts in (now - timedelta(days=1), now - timedelta(days=30)):
        database.execute_sql(
            "INSERT INTO forecast_data (prediction_time, target_time_start, target_time_end,"
            " country, source_api, created_at) VALUES (:t, :t, :t, 'singapore', 'test', :t)",
            {"t": ts.isoformat()},
        )

    response = client.get("/api/forecasts/compare?country=singapore&days_back=7")

    assert response.status_code == 200
    assert response.json()["official_forecast_count"] == 1
