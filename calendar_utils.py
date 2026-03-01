"""
Jewish Calendar Utility Functions

This module provides utility functions for working with Jewish calendar events,
including finding event sequences, calculating times, and determining event dates.
"""

from datetime import date, datetime, timedelta
from functools import lru_cache
from typing import Any, Dict, Optional

from jewcal import JewCal
from jewcal.models.zmanim import Location


@lru_cache(maxsize=128)
def _get_jewcal_cached(gregorian_date: date, diaspora: bool = False) -> JewCal:
    """Get a cached JewCal instance for a specific date (without location).

    Args:
        gregorian_date: The Gregorian date
        diaspora: Whether to use diaspora customs (default: False for Israel)

    Returns:
        A JewCal instance for the given date
    """
    return JewCal(gregorian_date=gregorian_date, diaspora=diaspora)


@lru_cache(maxsize=128)
def _get_jewcal_with_location_cached(
    gregorian_date: date,
    diaspora: bool,
    lat: float,
    lon: float,
    candle_offset: int
) -> JewCal:
    """Get a cached JewCal instance with location for a specific date.

    Location objects are not hashable, so we cache based on the location parameters
    and create the Location object inside this function.

    Args:
        gregorian_date: The Gregorian date
        diaspora: Whether to use diaspora customs
        lat: Latitude
        lon: Longitude
        candle_offset: Minutes before sunset for candle lighting

    Returns:
        A JewCal instance for the given date with location
    """
    location = Location(
        latitude=lat,
        longitude=lon,
        use_tzeis_hakochavim=True,
        hadlokas_haneiros_minutes=candle_offset,
        tzeis_minutes=42
    )
    return JewCal(gregorian_date=gregorian_date, diaspora=diaspora, location=location)


def clear_jewcal_cache() -> None:
    """Clear the JewCal cache. Useful for testing."""
    _get_jewcal_cached.cache_clear()
    _get_jewcal_with_location_cached.cache_clear()


def next_friday(d: date) -> date:
    """
    Find the next Friday from a given date.
    
    Args:
        d: The starting date
        
    Returns:
        The next Friday date
    """
    days_ahead = (4 - d.weekday()) % 7
    if days_ahead == 0 and datetime.now().hour >= 12:
        days_ahead = 7
    return d + timedelta(days=days_ahead)


def is_end_of_holiday_sequence(target_date: date) -> bool:
    """
    Check if target_date is the end of a holiday sequence (should have havdalah).

    A sequence ends when the next day does not have candle lighting or havdalah.

    Args:
        target_date: Date to check

    Returns:
        True if this is the last day of the sequence
    """
    next_day = target_date + timedelta(days=1)
    next_jewcal = _get_jewcal_cached(next_day, False)

    # If next day has events that require candle lighting, current day is not the end
    if (next_jewcal.has_events() and
        next_jewcal.events.action in ["Candles", "Havdalah"]):
        return False

    return True


def find_event_sequence(start_date: date) -> tuple[date, date, str, str]:
    """Find a complete event sequence (Shabbat or holiday sequence).
    Returns: (start_date, end_date, event_type, event_name)
    """
    current_date = start_date
    sequence_start = start_date
    sequence_end = start_date
    main_event_type = None
    main_event_name = None

    # Find the start of the sequence (if we're in the middle)
    # Only go back if the previous day is part of a continuous sequence
    while True:
        prev_day = current_date - timedelta(days=1)
        prev_jewcal = _get_jewcal_cached(prev_day, False)

        # Only continue backwards if:
        # 1. Previous day has events
        # 2. Previous day does NOT end with Havdalah (meaning it continues to current day)
        if (prev_jewcal.has_events() and
            prev_jewcal.events.action in ["Candles", "Havdalah"]):
            # If previous day ends with Havdalah, it's a separate sequence
            if prev_jewcal.events.action == "Havdalah":
                break
            # Otherwise, continue backwards
            current_date = prev_day
            sequence_start = prev_day
        else:
            break

    # Find the end of the sequence
    current_date = start_date
    while True:
        jewcal = _get_jewcal_cached(current_date, False)

        if jewcal.has_events():
            if jewcal.events.yomtov:
                main_event_type = "yomtov"
                main_event_name = jewcal.events.yomtov
            elif jewcal.events.shabbos:
                main_event_type = "shabbos"
                main_event_name = jewcal.events.shabbos

            sequence_end = current_date

            # Check if sequence continues - only if current day is NOT the end (no Havdalah)
            # OR if the next day is the immediate continuation (like Yom Tov followed by Shabbat on the same day)
            next_day = current_date + timedelta(days=1)
            next_jewcal = _get_jewcal_cached(next_day, False)

            # Only continue if:
            # 1. Current day doesn't end with Havdalah (meaning it continues to next day)
            # 2. OR next day has Candles AND current day action is Candles (continuous sequence)
            if (next_jewcal.has_events() and
                next_jewcal.events.action in ["Candles", "Havdalah"]):
                # If current day has Havdalah, the sequence ends here (no continuation)
                if jewcal.events.action == "Havdalah":
                    break
                # Otherwise, continue to next day
                current_date = next_day
            else:
                break
        else:
            break

    return sequence_start, sequence_end, main_event_type, main_event_name


def find_next_sequence(start_base: date) -> tuple[date, date, str, str]:
    """Find the next event sequence starting from start_base.
    Returns: (start_date, end_date, event_type, event_name)
    """
    current_date = start_base

    # Check up to 14 days ahead to find the next event
    for i in range(14):
        check_date = current_date + timedelta(days=i)

        # Create a temporary jewcal object to check for events
        temp_jewcal = _get_jewcal_cached(check_date, False)

        if temp_jewcal.has_events():
            # Check if this is an event that requires candle lighting (prioritize Yom Tov)
            if temp_jewcal.events.action in ["Candles", "Havdalah"]:
                # Found an event, now find the complete sequence
                return find_event_sequence(check_date)

    # Fallback to next Friday if no special events found
    next_friday_date = next_friday(start_base)
    return find_event_sequence(next_friday_date)


def find_next_event_date(start_base: date) -> tuple[date, str, str]:
    """Find the next Shabbat or Yom Tov event starting from start_base."""
    current_date = start_base

    # Check up to 14 days ahead to find the next event
    for i in range(14):
        check_date = current_date + timedelta(days=i)

        # Create a temporary jewcal object to check for events
        temp_jewcal = _get_jewcal_cached(check_date, False)

        if temp_jewcal.has_events():
            # Check if this is an event that requires candle lighting (prioritize Yom Tov)
            if temp_jewcal.events.action in ["Candles", "Havdalah"]:
                if temp_jewcal.events.yomtov:
                    event_type = "yomtov"
                    event_name = temp_jewcal.events.yomtov
                else:
                    event_type = "shabbos"
                    event_name = temp_jewcal.events.shabbos
                return check_date, event_type, event_name

    # Fallback to next Friday if no special events found
    return next_friday(start_base), "shabbos", "Shabbos"


def jewcal_times_for_date(lat: float, lon: float, target_date: date, candle_offset: int) -> dict:
    """Calculate Shabbat/Yom Tov times using jewcal library for accurate local calculations."""
    # Import here to avoid circular dependency
    from make_shabbat_posts import get_parsha_from_hebcal

    # Get JewCal info for the target date (Israel customs since we're in Israel)
    # Use cached version with location parameters
    jewcal = _get_jewcal_with_location_cached(target_date, False, lat, lon, candle_offset)

    # Determine event type and get appropriate times
    event_name = None
    event_type = None
    candle_time = None
    havdalah_time = None

    if jewcal.has_events():
        # Check what type of event this is (prioritize Yom Tov over Shabbat)
        if jewcal.events.yomtov:
            event_name = jewcal.events.yomtov
            event_type = "yomtov"
        elif jewcal.events.shabbos:
            event_name = jewcal.events.shabbos
            event_type = "shabbos"

        # Get zmanim if available
        if jewcal.zmanim:
            zmanim_dict = jewcal.zmanim.to_dict()

            # Get candle lighting time for Shabbat or Yom Tov with candles
            if (event_type == "shabbos" or jewcal.events.action == "Candles"):
                if zmanim_dict.get('hadlokas_haneiros'):
                    candle_time = zmanim_dict['hadlokas_haneiros']

            # Get havdalah time for regular Shabbat or end of holiday sequence
            if (event_type == "shabbos" or
                (event_type == "yomtov" and is_end_of_holiday_sequence(target_date))):
                if zmanim_dict.get('tzeis_hakochavim'):
                    havdalah_time = zmanim_dict['tzeis_hakochavim']
                elif zmanim_dict.get('tzeis_minutes'):
                    havdalah_time = zmanim_dict['tzeis_minutes']

    # Get parsha information only if this involves Shabbat
    parsha = None
    if (event_type == "shabbos" or
        (event_type == "yomtov" and target_date.weekday() == 5)):  # Friday = 4, Saturday = 5
        parsha = get_parsha_from_hebcal(target_date)

    return {
        "parsha": parsha,
        "event_name": event_name,
        "event_type": event_type,
        "candle": candle_time if candle_time else None,
        "havdalah": havdalah_time if havdalah_time else None,
        "action": jewcal.events.action if jewcal.has_events() else None
    }


def jewcal_times_for_sequence(
    lat: float,
    lon: float,
    start_date: date,
    end_date: date,
    candle_offset: int
) -> Dict[str, Any]:
    """
    Calculate times for a complete event sequence (Shabbat or holiday sequence).

    This handles multi-day sequences like Yom Tov followed by Shabbat, returning
    the candle lighting time from the first day and havdalah from the last day.

    Args:
        lat: Latitude of the location
        lon: Longitude of the location
        start_date: First day of the sequence
        end_date: Last day of the sequence
        candle_offset: Minutes before sunset for candle lighting

    Returns:
        Dict with keys: parsha, event_name, event_type, candle, havdalah,
        start_date, end_date, action
    """
    # Import here to avoid circular dependency
    from make_shabbat_posts import get_parsha_from_hebcal

    # Get candle lighting time from the start of the sequence
    # Use cached version with location parameters
    start_jewcal = _get_jewcal_with_location_cached(start_date, False, lat, lon, candle_offset)
    candle_time = None
    if start_jewcal.zmanim:
        start_zmanim = start_jewcal.zmanim.to_dict()
        if start_zmanim.get('hadlokas_haneiros'):
            candle_time = start_zmanim['hadlokas_haneiros']

    # Get havdalah time from the end of the sequence
    end_jewcal = _get_jewcal_with_location_cached(end_date, False, lat, lon, candle_offset)
    havdalah_time = None
    if end_jewcal.zmanim:
        end_zmanim = end_jewcal.zmanim.to_dict()
        if end_zmanim.get('tzeis_hakochavim'):
            havdalah_time = end_zmanim['tzeis_hakochavim']
        elif end_zmanim.get('tzeis_minutes'):
            havdalah_time = end_zmanim['tzeis_minutes']

    # Determine event type and name
    # Prefer the end event if it's more significant (e.g., Simchat Torah over Hoshana Rabba)
    event_name = None
    event_type = None

    # Check both start and end events
    start_event_name = None
    start_event_type = None
    end_event_name = None
    end_event_type = None

    if start_jewcal.has_events():
        if start_jewcal.events.yomtov:
            start_event_type = "yomtov"
            start_event_name = start_jewcal.events.yomtov
        elif start_jewcal.events.shabbos:
            start_event_type = "shabbos"
            start_event_name = start_jewcal.events.shabbos

    if end_jewcal.has_events():
        if end_jewcal.events.yomtov:
            end_event_type = "yomtov"
            end_event_name = end_jewcal.events.yomtov
        elif end_jewcal.events.shabbos:
            end_event_type = "shabbos"
            end_event_name = end_jewcal.events.shabbos

    # Prefer end event if it's a major holiday (Simchat Torah, Shmini Atzeret, etc.)
    # Otherwise use start event
    if end_event_name and ("Simchat Tora" in end_event_name or "Shmini Atzeret" in end_event_name):
        event_type = end_event_type
        event_name = end_event_name
    else:
        event_type = start_event_type
        event_name = start_event_name

    # Get parsha information only if sequence involves Shabbat
    parsha = None
    if (event_type == "shabbos" or
        any((start_date + timedelta(days=i)).weekday() == 5
            for i in range((end_date - start_date).days + 1))):
        parsha = get_parsha_from_hebcal(start_date)

    return {
        "parsha": parsha,
        "event_name": event_name,
        "event_type": event_type,
        "candle": candle_time if candle_time else None,
        "havdalah": havdalah_time if havdalah_time else None,
        "start_date": start_date,
        "end_date": end_date,
        "action": start_jewcal.events.action if start_jewcal.has_events() else None
    }

