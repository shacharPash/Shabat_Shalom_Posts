"""
Hebcal API integration for fetching parsha information.

This module provides functions to interact with the Hebcal API to retrieve
Torah portion (parsha) information for specific dates. It includes caching
to minimize API calls and helper functions for date calculations.

Hebcal provides authoritative Israel readings, with bundled local data
as an exact-date fallback when the API cannot provide a reading.
"""

import json
import os
import time
from contextlib import contextmanager
from contextvars import ContextVar
from collections.abc import Iterator
from datetime import date, timedelta
from typing import Any, Dict, Optional

import requests
from jewcal import JewCal

from translations import translate_parsha
from calendar_utils import get_full_yomtov_name

# Timezone constant for Hebcal API
TZID = "Asia/Jerusalem"


# ========= LOCAL PARSHA DATA =========
# Load local parsha data for fast lookups without API calls
# Key: date string (YYYY-MM-DD), Value: parsha name (English)
_LOCAL_PARSHA_DATA: Dict[str, str] = {}
_parsha_file = os.path.join(os.path.dirname(__file__), 'parsha_data.json')
if os.path.exists(_parsha_file):
    try:
        with open(_parsha_file, 'r', encoding='utf-8') as f:
            _LOCAL_PARSHA_DATA = json.load(f)
    except Exception as e:
        print(f"Warning: Could not load local parsha data: {e}")


# ========= HEBCAL API CACHE =========
# Cache to store Hebcal API responses by year - avoids redundant API calls
# Key: year (int), Value: API response data (dict)
_hebcal_cache: Dict[int, Dict[str, Any]] = {}
_failure_cache: Dict[int, float] = {}
FAILURE_CACHE_SECONDS = 60
MAX_FAILURE_YEARS = 128
FETCH_TIMEOUT = (2, 3)
_sequence_cache: ContextVar[Optional[dict[int, Optional[Dict[str, Any]]]]] = ContextVar(
    'hebcal_sequence', default=None)


@contextmanager
def hebcal_request_sequence() -> Iterator[None]:
    """Attempt each year once in a request, even if the failure TTL expires."""
    token = _sequence_cache.set({})
    try:
        yield
    finally:
        _sequence_cache.reset(token)


def _get_hebcal_data_for_year(year: int) -> Optional[Dict[str, Any]]:
    """
    Get Hebcal API data for a specific year, using cache when available.

    Args:
        year: The year to fetch data for

    Returns:
        Hebcal API response data, or None if fetch failed
    """
    sequence = _sequence_cache.get()
    if sequence is not None and year in sequence:
        return sequence[year]
    if year in _hebcal_cache:
        return _hebcal_cache[year]
    now = time.monotonic()
    for failed_year, expiry in list(_failure_cache.items()):
        if expiry <= now:
            _failure_cache.pop(failed_year, None)
    if year in _failure_cache:
        if sequence is not None:
            sequence[year] = None
        return None

    response = None
    data = None
    try:
        response = requests.get(_build_hebcal_url(year), timeout=FETCH_TIMEOUT)
        response.raise_for_status()
        candidate = response.json()
        if not isinstance(candidate, dict) or not isinstance(candidate.get('items'), list):
            raise ValueError('Malformed calendar response')
        if not all(isinstance(item, dict) for item in candidate['items']):
            raise ValueError('Malformed calendar items')
        data = candidate
        _hebcal_cache[year] = data
    except Exception:
        if len(_failure_cache) >= MAX_FAILURE_YEARS:
            _failure_cache.pop(next(iter(_failure_cache)))
        _failure_cache[year] = time.monotonic() + FAILURE_CACHE_SECONDS
    finally:
        if response is not None:
            response.close()
    if sequence is not None:
        sequence[year] = data
    return data


def clear_hebcal_cache() -> None:
    """Clear the Hebcal API cache. Useful for testing or memory management."""
    _hebcal_cache.clear()
    _failure_cache.clear()


def get_parsha_from_hebcal(target_date: date) -> Optional[str]:
    """
    Get parsha information for the week containing target_date.

    Uses authoritative Hebcal data, then an exact-date local fallback.
    Festival Saturdays have no regular weekly parsha, even if a stale local
    snapshot contains one. Readings are never borrowed from another week.

    Args:
        target_date: The date to get parsha for

    Returns:
        Hebrew parsha name with prefix, or None if not found
    """
    # Check the actual Saturday, not the eve or another day in the sequence.
    saturday = _get_saturday_for_date(target_date)
    if get_full_yomtov_name(saturday):
        return None

    jewcal_obj = JewCal(gregorian_date=saturday, diaspora=False)
    if jewcal_obj.has_events() and jewcal_obj.events.yomtov:
        event_name = jewcal_obj.events.yomtov
        # Shabbat Chol HaMoed (Pesach or Sukkot) has no regular parsha
        if "Chol HaMoed" in event_name:
            return None

    # Use Hebcal as the authoritative source first. The bundled local data is
    # only a fallback, because an older generated snapshot may contain diaspora
    # readings for weeks when Israel and the diaspora are out of sync.
    data = _get_hebcal_data_for_year(saturday.year)
    if data:
        # Find the parsha for our specific Saturday
        parsha_title = _find_parsha_for_date(data, saturday)
        if parsha_title:
            parsha_clean = parsha_title.replace("Parashat ", "").strip()
            return translate_parsha(parsha_clean)

    # Fallback: use bundled local parsha data when the API is unavailable.
    date_key = saturday.isoformat()  # YYYY-MM-DD format
    if date_key in _LOCAL_PARSHA_DATA:
        parsha_english = _LOCAL_PARSHA_DATA[date_key]
        return translate_parsha(parsha_english)

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
        f"&tzid={TZID}&s=on&i=on"
    )


def _find_parsha_for_date(data: Dict[str, Any], saturday: date) -> Optional[str]:
    """Find the parsha title for a specific Saturday in Hebcal data."""
    target_date_str = saturday.isoformat()
    for item in data.get("items", []):
        if item.get("category") == "parashat" and item.get("date") == target_date_str:
            return item.get("title")
    return None
