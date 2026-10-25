import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import locations


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("ADMIN_SECRET", "s3cret")
    app = FastAPI()
    app.include_router(locations.router, prefix="/api")
    return TestClient(app)


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/api/locations"),
        ("post", "/api/locations"),
        ("get", "/api/locations/1"),
        ("delete", "/api/locations/1"),
        ("post", "/api/locations/1/refresh"),
    ],
)
def test_locations_crud_without_secret_is_forbidden(client, method, path):
    response = client.request(method, path, json={"latitude": 1.3, "longitude": 103.8})

    assert response.status_code == 403


def test_locations_list_with_wrong_secret_is_forbidden(client):
    response = client.get("/api/locations", headers={"X-Admin-Secret": "nope"})

    assert response.status_code == 403


def test_locations_list_with_secret_reaches_handler(client, monkeypatch):
    class _Conn:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def execute(self, *args, **kwargs):
            class _Result:
                def fetchall(self):
                    return []

            return _Result()

    class _Engine:
        def connect(self):
            return _Conn()

    monkeypatch.setattr(locations, "get_engine", lambda: _Engine())

    response = client.get("/api/locations", headers={"X-Admin-Secret": "s3cret"})

    assert response.status_code == 200
    assert response.json() == {"locations": []}


def test_locations_list_is_forbidden_when_admin_secret_unset(client, monkeypatch):
    monkeypatch.delenv("ADMIN_SECRET")

    response = client.get("/api/locations", headers={"X-Admin-Secret": "s3cret"})

    assert response.status_code == 403
