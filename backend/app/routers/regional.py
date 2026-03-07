"""
Regional Weather API router for Malaysian and Indonesian cities.

Provides endpoints for fetching regional weather data with search functionality.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.services.regional_weather_service import (
    get_regional_weather_service,
    RegionalAPIError
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/regional", tags=["regional"])


@router.get("/cities")
async def get_regional_cities(search: Optional[str] = Query(default=None, max_length=100)):
    """
    Get weather data for regional cities in Singapore, Malaysia, and Indonesia.
    
    Returns weather information for ~25-30 cities across the region with optional
    search filtering. Data is cached for 30 minutes to minimize API calls.
    
    Args:
        search: Optional search term to filter cities by name or country (case-insensitive)
        
    Returns:
        JSON response with city weather data and cache timestamp
        
    Example response:
        {
            "cities": [
                {
                    "id": "singapore",
                    "name": "Singapore",
                    "country": "Singapore",
                    "temperature": 28.5,
                    "condition": "Partly Cloudy",
                    "humidity": 75,
                    "windSpeed": 12,
                    "lastUpdated": "2024-01-15T10:00:00+00:00"
                },
                {
                    "id": "kuala-lumpur",
                    "name": "Kuala Lumpur",
                    "country": "Malaysia",
                    "temperature": 27.0,
                    "condition": "Thunderstorms",
                    "humidity": 82,
                    "windSpeed": 8,
                    "lastUpdated": "2024-01-15T10:00:00+00:00"
                }
            ],
            "cachedAt": "2024-01-15T09:45:00+00:00",
            "count": 28
        }
    """
    try:
        regional_service = get_regional_weather_service()
        cities = await regional_service.get_regional_cities()
        
        # Apply server-side search filtering if search parameter provided
        if search:
            search_lower = search.lower().strip()
            cities = [
                city for city in cities
                if search_lower in city.name.lower() or search_lower in city.country.lower()
            ]
            logger.info(f"Filtered to {len(cities)} cities matching search: '{search}'")
        
        # Convert to dict format for JSON response
        city_dicts = [city.to_dict() for city in cities]
        
        # Get cache timestamp
        cached_at = regional_service.cache_timestamp
        cached_at_iso = cached_at.isoformat() if cached_at else None
        
        logger.info(f"Returning {len(city_dicts)} regional cities")
        
        return {
            "cities": city_dicts,
            "cachedAt": cached_at_iso,
            "count": len(city_dicts)
        }
        
    except RegionalAPIError as e:
        logger.error(f"Regional API error: {e}")
        # Try to return cached data if available
        regional_service = get_regional_weather_service()
        if regional_service.city_cache:
            logger.info("Returning stale cached cities after API error")
            cities = regional_service.city_cache
            
            # Apply search filter to cached data
            if search:
                search_lower = search.lower().strip()
                cities = [
                    city for city in cities
                    if search_lower in city.name.lower() or search_lower in city.country.lower()
                ]
            
            city_dicts = [city.to_dict() for city in cities]
            cached_at = regional_service.cache_timestamp
            cached_at_iso = cached_at.isoformat() if cached_at else None
            
            return {
                "cities": city_dicts,
                "cachedAt": cached_at_iso,
                "count": len(city_dicts),
                "stale": True
            }
        
        raise HTTPException(
            status_code=503,
            detail="Regional weather data temporarily unavailable"
        ) from e
        
    except Exception as e:
        logger.error(f"Unexpected error fetching regional cities: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        ) from e
