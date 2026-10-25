import os
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.admin_auth import admin_header
from app.db.database import get_engine

from app.services.weather_api import SingaporeWeatherClient, WeatherProviderError

router = APIRouter(prefix="/locations", tags=["locations"])

def _fetch_location(conn, location_id: int):
    return conn.execute(
        text("SELECT * FROM locations WHERE id = :id"), {"id": location_id}
    ).fetchone()


def row_to_dict(row):
    if row is None:
        return None
    d = dict(row._mapping)
    weather = {
        "condition": d.pop("weather_condition", None),
        "observed_at": d.pop("weather_observed_at", None),
        "source": d.pop("weather_source", None),
        "area": d.pop("weather_area", None),
        "valid_period_text": d.pop("weather_valid_period_text", None),
    }
    d.pop("weather_refreshed_at", None)
    d["weather"] = weather
    return d


@router.get("", dependencies=[Depends(admin_header)])
def list_locations():
    with get_engine().connect() as conn:
        rows = conn.execute(
            text("SELECT * FROM locations ORDER BY created_at DESC, id DESC")
        ).fetchall()
    return {"locations": [row_to_dict(row) for row in rows]}


@router.get("/areas/nearest")
def nearest_area(lat: float, lng: float):
    """
    Return the nearest NEA forecast area name for given coordinates.
    Calls the 2-hour forecast API and finds the closest area label.
    Always returns a proper Singapore neighbourhood name.
    """
    api_key = os.getenv("WEATHERAPI_KEY")
    client = SingaporeWeatherClient(api_key=api_key)
    try:
        payload = client.fetch_latest_forecast_payload()
        data = payload.get("data") if isinstance(payload, dict) else None
        root = data if isinstance(data, dict) else payload
        area_metadata = root.get("area_metadata", [])
        name = client._nearest_area_name(area_metadata, lat, lng)
        if not name:
            raise WeatherProviderError("No area data found")
        return {"area": name, "source": "nea-2hr-forecast"}
    except WeatherProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("", status_code=status.HTTP_201_CREATED, dependencies=[Depends(admin_header)])
def create_location(payload: dict):
    latitude = payload.get("latitude")
    longitude = payload.get("longitude")

    if latitude is None or longitude is None:
        raise HTTPException(status_code=422, detail="latitude and longitude are required")
    if not (1.1 <= latitude <= 1.5 and 103.6 <= longitude <= 104.1):
        raise HTTPException(
            status_code=422,
            detail="Coordinates must be within Singapore (lat 1.1–1.5, lon 103.6–104.1)",
        )

    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S")
    try:
        with get_engine().begin() as conn:
            new_id = conn.execute(
                text("""INSERT INTO locations (latitude, longitude, created_at, weather_condition, weather_source)
                        VALUES (:lat, :lng, :now, 'Not refreshed', 'not-refreshed')
                        RETURNING id"""),
                {"lat": latitude, "lng": longitude, "now": now},
            ).scalar_one()
            row = _fetch_location(conn, new_id)
    except IntegrityError:
        raise HTTPException(status_code=409, detail="Location already exists") from None
    return row_to_dict(row)


@router.get("/{location_id}", dependencies=[Depends(admin_header)])
def get_location(location_id: int):
    with get_engine().connect() as conn:
        row = _fetch_location(conn, location_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Location not found")
    return row_to_dict(row)


@router.delete("/{location_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(admin_header)])
def delete_location(location_id: int):
    with get_engine().begin() as conn:
        deleted = conn.execute(
            text("DELETE FROM locations WHERE id = :id"), {"id": location_id}
        ).rowcount
    if not deleted:
        raise HTTPException(status_code=404, detail="Location not found")
    return None


@router.post("/{location_id}/refresh", dependencies=[Depends(admin_header)])
def refresh_location(location_id: int):
    with get_engine().connect() as conn:
        row = _fetch_location(conn, location_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Location not found")

    api_key = os.getenv("WEATHERAPI_KEY")  # Fixed: was WEATHER_API_KEY
    client = SingaporeWeatherClient(api_key=api_key)

    try:
        snapshot = client.get_current_weather(
            latitude=row.latitude,
            longitude=row.longitude,
        )
    except WeatherProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S")
    with get_engine().begin() as conn:
        conn.execute(
            text("""UPDATE locations
                    SET weather_condition = :condition, weather_observed_at = :observed_at,
                        weather_source = :source, weather_area = :area,
                        weather_valid_period_text = :valid_period_text, weather_refreshed_at = :now
                    WHERE id = :id"""),
            {
                "condition": snapshot["condition"],
                "observed_at": snapshot["observed_at"],
                "source": snapshot["source"],
                "area": snapshot["area"],
                "valid_period_text": snapshot["valid_period_text"],
                "now": now,
                "id": location_id,
            },
        )
        row = _fetch_location(conn, location_id)
    return row_to_dict(row)
