"""
Shared module for city data loading and management.

This module provides a centralized way to load city data from GeoJSON files,
avoiding code duplication across the codebase.
"""

import json
import os
from functools import lru_cache
from typing import Any, Dict, List, Tuple

# Type aliases for clarity
CityDict = Dict[str, Any]

# Candle lighting offset rules by city name
SPECIAL_OFFSET_CITIES: Dict[str, int] = {
    "ירושלים": 40,
    "פתח תקווה": 40,
    "חיפה": 30,
    "מורשת": 30,
}
DEFAULT_CANDLE_OFFSET = 20


def _get_candle_offset(city_name: str) -> int:
    """Get the default candle lighting offset for a city."""
    return SPECIAL_OFFSET_CITIES.get(city_name, DEFAULT_CANDLE_OFFSET)


@lru_cache(maxsize=1)
def load_cities_from_geojson(geojson_path: str = None) -> Tuple[List[CityDict], ...]:
    """
    Load and parse cities from the GeoJSON file.
    
    Returns a tuple (for hashability with lru_cache) of city dictionaries.
    Each city dict contains: name, lat, lon, candle_offset, population.
    
    The result is cached for performance - subsequent calls return the same data.
    """
    if geojson_path is None:
        # Try multiple possible locations for the GeoJSON file
        possible_paths = [
            "cities_coordinates.geojson",
            os.path.join(os.path.dirname(__file__), "cities_coordinates.geojson"),
        ]
        for path in possible_paths:
            if os.path.exists(path):
                geojson_path = path
                break
        else:
            print("Error: Could not find cities_coordinates.geojson")
            return tuple()
    
    try:
        with open(geojson_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        cities = []
        for feature in data.get("features", []):
            props = feature.get("properties", {})
            geometry = feature.get("geometry", {})
            coords = geometry.get("coordinates", [])

            name = props.get("MGLSDE_LOC", "").strip()
            population = props.get("MGLSDE_L_1", 0)
            
            if name and len(coords) >= 2:
                cities.append({
                    "name": name,
                    "lat": coords[1],  # GeoJSON uses [lon, lat]
                    "lon": coords[0],
                    "candle_offset": _get_candle_offset(name),
                    "population": population,
                })

        # Sort by population descending (cities first, then smaller settlements)
        cities.sort(key=lambda c: c["population"], reverse=True)
        return tuple(cities)
        
    except Exception as e:
        print(f"Error loading GeoJSON: {e}")
        return tuple()


def get_cities_list(geojson_path: str = None) -> List[CityDict]:
    """
    Get cities as a mutable list.
    
    This is a convenience wrapper that converts the cached tuple to a list.
    """
    return list(load_cities_from_geojson(geojson_path))


def build_city_lookup(cities: List[CityDict] = None) -> Dict[str, CityDict]:
    """
    Build a lookup dictionary mapping city names to their full data.
    
    Args:
        cities: Optional list of cities. If not provided, loads from GeoJSON.
    
    Returns:
        Dict mapping city name to city data.
    """
    if cities is None:
        cities = get_cities_list()
    return {city["name"]: city for city in cities}

