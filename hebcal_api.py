"""
Hebcal API integration for fetching parsha information.

This module provides functions to interact with the Hebcal API to retrieve
Torah portion (parsha) information for specific dates. It includes caching
to minimize API calls and helper functions for date calculations.
"""

from datetime import date, timedelta
from typing import Any, Dict, Optional

import requests
from jewcal import JewCal

from translations import translate_parsha

# Timezone constant for Hebcal API
TZID = "Asia/Jerusalem"


# ========= HEBCAL API CACHE =========
# Cache to store Hebcal API responses by year - avoids redundant API calls
# Key: year (int), Value: API response data (dict)
_hebcal_cache: Dict[int, Dict[str, Any]] = {}


def _get_hebcal_data_for_year(year: int) -> Optional[Dict[str, Any]]:
    """
    Get Hebcal API data for a specific year, using cache when available.

    Args:
        year: The year to fetch data for

    Returns:
        Hebcal API response data, or None if fetch failed
    """
    # Check cache first
    if year in _hebcal_cache:
        return _hebcal_cache[year]

    # Fetch from API
    url = _build_hebcal_url(year)
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()

        # Store in cache for future use
        _hebcal_cache[year] = data
        return data

    except Exception as e:
        print(f"Warning: Could not fetch Hebcal data for year {year}: {e}")
        return None


def clear_hebcal_cache() -> None:
    """Clear the Hebcal API cache. Useful for testing or memory management."""
    _hebcal_cache.clear()


def get_parsha_from_hebcal(target_date: date) -> Optional[str]:
    """
    Get parsha information from Hebcal API for the week containing target_date.

    Uses a cache to store API responses by year, significantly reducing
    the number of API calls when fetching multiple dates.

    Args:
        target_date: The date to get parsha for

    Returns:
        Hebrew parsha name with prefix, or None if not found
    """
    # Special cases for Torah reading during holidays
    jewcal_obj = JewCal(gregorian_date=target_date, diaspora=False)
    if jewcal_obj.has_events() and jewcal_obj.events.yomtov:
        event_name = jewcal_obj.events.yomtov
        # Simchat Torah, Hoshana Rabba, and Chol HaMoed Sukkot read "Vezot Haberakhah"
        if any(s in event_name for s in ("Simchat Tora", "Hoshana Rabba", "Chol HaMoed")):
            return "פרשת וזאת הברכה"

    # Find the Saturday of the week containing target_date
    saturday = _get_saturday_for_date(target_date)

    # Get cached or fresh data for the year
    data = _get_hebcal_data_for_year(saturday.year)
    if not data:
        return None

    # Find the parsha for our specific Saturday
    parsha_title = _find_parsha_for_date(data, saturday)
    if parsha_title:
        parsha_clean = parsha_title.replace("Parashat ", "").strip()
        return translate_parsha(parsha_clean)

    # If exact match not found, find the closest Saturday before our target
    parsha_title = _find_closest_parsha_before_date(data, saturday)
    if parsha_title:
        parsha_clean = parsha_title.replace("Parashat ", "").strip()
        return translate_parsha(parsha_clean)

    return None


def _get_saturday_for_date(target_date: date) -> date:
    """Get the Saturday of the week containing target_date."""
    days_until_saturday = (5 - target_date.weekday()) % 7  # Saturday is weekday 5
    if days_until_saturday == 0 and target_date.weekday() == 5:
        return target_date
    return target_date + timedelta(days=days_until_saturday)


def _build_hebcal_url(year: int) -> str:
    """Build the Hebcal API URL for a given year."""
    return (
        f"https://www.hebcal.com/hebcal?v=1&cfg=json&maj=on&min=on&mod=on&nx=on"
        f"&year={year}&month=x&ss=on&mf=on&c=on&geo=pos"
        f"&latitude=31.778117828230577&longitude=35.23599222120022"
        f"&tzid={TZID}&s=on"
    )


def _find_parsha_for_date(data: Dict[str, Any], saturday: date) -> Optional[str]:
    """Find the parsha title for a specific Saturday in Hebcal data."""
    target_date_str = saturday.isoformat()
    for item in data.get("items", []):
        if item.get("category") == "parashat" and item.get("date") == target_date_str:
            return item.get("title")
    return None


def _find_closest_parsha_before_date(data: Dict[str, Any], saturday: date) -> Optional[str]:
    """Find the parsha title closest to but not after the target Saturday."""
    closest_parsha = None
    closest_date = None

    for item in data.get("items", []):
        if item.get("category") != "parashat":
            continue
        item_date_str = item.get("date", "")
        if not item_date_str:
            continue
        try:
            item_date = date.fromisoformat(item_date_str)
            if item_date <= saturday and (closest_date is None or item_date > closest_date):
                closest_date = item_date
                closest_parsha = item.get("title")
        except ValueError:
            continue

    return closest_parsha

