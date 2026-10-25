from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db import database
from app.db.migrations import migrate_forecast_tables, migrate_ml_tables
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


@pytest.fixture
def sqlite_db(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setattr(database, "_database_url", None)
    monkeypatch.setattr(database, "_engine", None)
    from app.main import init_db

    init_db()
    migrate_ml_tables()
    migrate_forecast_tables()


@pytest.fixture
def forecast_rows(sqlite_db):
    now = datetime.now(timezone.utc)
    for ts in (now - timedelta(days=1), now - timedelta(days=30)):
        database.execute_sql(
            "INSERT INTO forecast_data (prediction_time, target_time_start, target_time_end,"
            " country, source_api, created_at) VALUES (:t, :t, :t, 'singapore', 'test', :t)",
            {"t": ts.isoformat()},
        )


def test_forecast_compare_returns_recent_rows(client, forecast_rows):
    response = client.get("/api/forecasts/compare?country=singapore&days_back=7")

    assert response.status_code == 200
    assert response.json()["official_forecast_count"] == 1


def test_forecast_latest_filters_and_limits(client, forecast_rows):
    response = client.get("/api/forecasts/latest?country=singapore&limit=1")

    assert response.status_code == 200
    assert response.json()["count"] == 1
    assert response.json()["forecasts"][0]["country"] == "singapore"


def test_model_version_lookup_and_activation(client, sqlite_db):
    database.execute_sql(
        "INSERT INTO model_metadata (semantic_version, model_name, model_type, weather_parameter,"
        " country, version, hyperparameters, training_date, training_samples, validation_mae,"
        " validation_rmse, validation_mape, file_path, created_at) VALUES ('v1', 'm', 'prophet', 'rainfall',"
        " 'singapore', '1', '{}', '2026-01-01', 1, 0.1, 0.1, 0.1, 'm.pkl', '2026-01-01')"
    )
    admin = {"X-Admin-Secret": "s3cret"}

    assert client.get("/api/ml/versions?model_name=m").json()[0]["semantic_version"] == "v1"
    assert client.post("/api/ml/versions/v1/activate?model_name=m", headers=admin).status_code == 200
    assert client.get("/api/ml/current-model?model_name=m").json()["semantic_version"] == "v1"
    assert client.get("/api/ml/performance-history?model_name=m&limit=5").status_code == 200


def test_performance_record_and_stats(client, sqlite_db):
    admin = {"X-Admin-Secret": "s3cret"}
    target = datetime.now(timezone.utc).isoformat()
    created = client.post(
        "/api/performance/record-prediction",
        headers=admin,
        json={
            "location_id": 1, "prediction_timestamp": target, "target_timestamp": target,
            "hours_ahead": 1, "ml_temperature": 30.0, "official_temperature": 31.0,
            "ml_condition": "rain", "official_condition": "sunny",
        },
    )
    assert created.status_code == 200 and created.json()["id"]

    actual = client.post(
        "/api/performance/record-actual",
        headers=admin,
        json={"timestamp": target, "temperature": 30.2, "condition": "rain"},
    )
    assert actual.json()["predictions_evaluated"] == 1

    stats = client.get("/api/performance/stats").json()
    assert stats["total_predictions"] == 1
    assert stats["ml_performance"]["wins"] == 1
    assert client.get("/api/performance/history").json()["predictions"][0]["ml_wins"] == 1
    assert client.get("/api/performance/leaderboard").status_code == 200
