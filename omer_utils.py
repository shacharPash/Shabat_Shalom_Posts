"""
Sefirat HaOmer (Counting of the Omer) Utility Functions

This module provides utility functions for calculating and displaying the
Sefirat HaOmer count, which spans 49 days from 16 Nisan (second day of Pesach)
to Shavuot.

The counting follows the formula:
- Day 1: חֶסֶד שֶׁבְּחֶסֶד (Chesed of Chesed)
- Day 7: מַלְכוּת שֶׁבְּחֶסֶד (Malchut of Chesed)
- Day 8: חֶסֶד שֶׁבְּגְּבוּרָה (Chesed of Gevurah)
- etc.
"""

from datetime import date, datetime, timedelta
from functools import lru_cache
from typing import Optional, Tuple

import pytz
from jewcal import JewCal
from jewcal.models.zmanim import Location

# Israel timezone for converting UTC times
ISRAEL_TZ = pytz.timezone("Asia/Jerusalem")

# Jerusalem coordinates for sunset calculations
JERUSALEM_LAT = 31.7683
JERUSALEM_LON = 35.2137

# The 7 Sefirot in order
SEFIROT = [
    "חֶסֶד",      # Chesed - Day 1, 8, 15, 22, 29, 36, 43
    "גְּבוּרָה",   # Gevurah - Day 2, 9, 16, 23, 30, 37, 44
    "תִּפְאֶרֶת",  # Tiferet - Day 3, 10, 17, 24, 31, 38, 45
    "נֶצַח",      # Netzach - Day 4, 11, 18, 25, 32, 39, 46
    "הוֹד",       # Hod - Day 5, 12, 19, 26, 33, 40, 47
    "יְסוֹד",     # Yesod - Day 6, 13, 20, 27, 34, 41, 48
    "מַלְכוּת",   # Malchut - Day 7, 14, 21, 28, 35, 42, 49
]

# Hebrew number words for the Omer count
HEBREW_ONES = ["", "אֶחָד", "שְׁנַיִם", "שְׁלֹשָׁה", "אַרְבָּעָה", "חֲמִשָּׁה",
               "שִׁשָּׁה", "שִׁבְעָה", "שְׁמוֹנָה", "תִּשְׁעָה"]
HEBREW_TENS = ["", "עֲשָׂרָה", "עֶשְׂרִים", "שְׁלוֹשִׁים", "אַרְבָּעִים"]

# Special numbers
HEBREW_SPECIAL = {
    10: "עֲשָׂרָה",
    11: "אַחַד עָשָׂר",
    12: "שְׁנֵים עָשָׂר",
    13: "שְׁלֹשָׁה עָשָׂר",
    14: "אַרְבָּעָה עָשָׂר",
    15: "חֲמִשָּׁה עָשָׂר",
    16: "שִׁשָּׁה עָשָׂר",
    17: "שִׁבְעָה עָשָׂר",
    18: "שְׁמוֹנָה עָשָׂר",
    19: "תִּשְׁעָה עָשָׂר",
}


@lru_cache(maxsize=64)
def _find_omer_start_for_year(year: int) -> Optional[date]:
    """
    Find the Gregorian date of 16 Nisan (start of Omer) for a given Hebrew year.
    
    We search around Pesach time (March-April) to find 16 Nisan.
    
    Args:
        year: The Gregorian year to search in
        
    Returns:
        The date of 16 Nisan, or None if not found
    """
    # 16 Nisan is typically in March or April
    # Search from March 15 to April 30
    search_start = date(year, 3, 15)
    search_end = date(year, 4, 30)
    
    current = search_start
    while current <= search_end:
        jewcal_obj = JewCal(gregorian_date=current, diaspora=False)
        # Check if this is 16 Nisan (day=16, month=1 which is Nisan)
        if jewcal_obj.jewish_date.day == 16 and jewcal_obj.jewish_date.month == 1:
            return current
        current += timedelta(days=1)
    
    return None


def get_omer_day(target_date: date, after_midnight: bool = False) -> Optional[int]:
    """
    Calculate which day of the Omer (1-49) corresponds to a given date.
    
    The Omer is counted for 49 days starting from 16 Nisan (second day of Pesach).
    The counting is done at night (after sunset), so:
    - If after_midnight=False: returns the Omer day for the current evening
    - If after_midnight=True: returns the Omer day for the next evening
      (since after midnight we're still in the same halachic "day")
    
    Args:
        target_date: The Gregorian date to check
        after_midnight: If True, count for the next day (00:00+ is still "today" halachically)
        
    Returns:
        The Omer day (1-49), or None if not in the Omer period
    """
    # If after midnight, we're counting for the next calendar day's evening
    effective_date = target_date + timedelta(days=1) if after_midnight else target_date
    
    # Find the start of Omer for this year
    omer_start = _find_omer_start_for_year(effective_date.year)
    if not omer_start:
        return None
    
    # Calculate the Omer day
    # Day 1 is the evening of 16 Nisan (so 16 Nisan date = day 1)
    delta = (effective_date - omer_start).days + 1
    
    if delta < 1 or delta > 49:
        return None
    
    return delta


def get_sefirah_text(day: int) -> str:
    """
    Get the Sefirah text for a given Omer day.
    
    The formula is:
    - Lower sefirah (inner): (day - 1) % 7 -> index in SEFIROT
    - Upper sefirah (outer/week): (day - 1) // 7 -> index in SEFIROT
    
    Example: Day 1 = חסד שבחסד, Day 7 = מלכות שבחסד, Day 8 = חסד שבגבורה
    
    Args:
        day: The Omer day (1-49)
        
    Returns:
        The Sefirah text in Hebrew (e.g., "חֶסֶד שֶׁבְּחֶסֶד")
    """
    if day < 1 or day > 49:
        raise ValueError(f"Omer day must be 1-49, got {day}")
    
    lower_index = (day - 1) % 7   # Inner sefirah (day of week)
    upper_index = (day - 1) // 7  # Outer sefirah (week number)
    
    lower_sefirah = SEFIROT[lower_index]
    upper_sefirah = SEFIROT[upper_index]
    
    return f"{lower_sefirah} שֶׁבְּ{upper_sefirah}"


def _hebrew_number(n: int) -> str:
    """Convert a number (1-49) to Hebrew text for Omer counting."""
    if n in HEBREW_SPECIAL:
        return HEBREW_SPECIAL[n]

    if n < 10:
        return HEBREW_ONES[n]

    tens = n // 10
    ones = n % 10

    if ones == 0:
        return HEBREW_TENS[tens]

    return f"{HEBREW_ONES[ones]} וְ{HEBREW_TENS[tens]}"


def get_omer_count_text(day: int, nusach: str = "sefard") -> str:
    """
    Get the full Hebrew counting text for a given Omer day.

    Args:
        day: The Omer day (1-49)
        nusach: The nusach (liturgical tradition) to use:
            - "sefard" (default): "לָעֹמֶר" at the end
            - "ashkenaz": "בָּעֹמֶר" at the end
            - "edot_hamizrach": "לָעֹמֶר" after day count, before week breakdown

    Returns:
        The full Hebrew counting text (e.g., "הַיּוֹם יוֹם אֶחָד לָעֹמֶר")
    """
    if day < 1 or day > 49:
        raise ValueError(f"Omer day must be 1-49, got {day}")

    if nusach not in ("sefard", "ashkenaz", "edot_hamizrach"):
        raise ValueError(f"Invalid nusach: {nusach}. Must be 'sefard', 'ashkenaz', or 'edot_hamizrach'")

    # Determine the omer suffix based on nusach
    omer_suffix = "בָּעֹמֶר" if nusach == "ashkenaz" else "לָעֹמֶר"

    # Handle weeks and days
    weeks = day // 7
    remaining_days = day % 7

    # Build the count text
    day_text = _hebrew_number(day)

    # For edot_hamizrach, the structure is different - omer comes after day count
    if nusach == "edot_hamizrach":
        return _build_edot_hamizrach_text(day, day_text, weeks, remaining_days)

    # Sefard and Ashkenaz have the same structure, just different suffix
    if day == 1:
        return f"הַיּוֹם יוֹם {day_text} {omer_suffix}"

    # Days 2-6: "היום X ימים לעומר/בעומר"
    if day < 7:
        return f"הַיּוֹם {day_text} יָמִים {omer_suffix}"

    # Day 7: "היום שבעה ימים שהם שבוע אחד לעומר/בעומר"
    if day == 7:
        return f"הַיּוֹם {day_text} יָמִים שֶׁהֵם שָׁבוּעַ אֶחָד {omer_suffix}"

    # Days 8-49: Include weeks
    if remaining_days == 0:
        # Exact weeks
        week_text = _hebrew_week_text(weeks)
        return f"הַיּוֹם {day_text} יוֹם שֶׁהֵם {week_text} {omer_suffix}"
    else:
        # Weeks and days
        week_text = _hebrew_week_text(weeks)
        remaining_text = _hebrew_day_text(remaining_days)
        return f"הַיּוֹם {day_text} יוֹם שֶׁהֵם {week_text} וְ{remaining_text} {omer_suffix}"


def _build_edot_hamizrach_text(day: int, day_text: str, weeks: int, remaining_days: int) -> str:
    """
    Build the Omer count text for Edot HaMizrach nusach.

    In this nusach, "לָעֹמֶר" comes after the day count, before the week breakdown.
    Example: "היום 8 יום לעומר שהם שבוע אחד ויום אחד"
    """
    omer_suffix = "לָעֹמֶר"

    if day == 1:
        return f"הַיּוֹם יוֹם {day_text} {omer_suffix}"

    # Days 2-6: "היום X ימים לעומר" (same as sefard, no week breakdown)
    if day < 7:
        return f"הַיּוֹם {day_text} יָמִים {omer_suffix}"

    # Day 7: "היום שבעה ימים לעומר שהם שבוע אחד"
    if day == 7:
        return f"הַיּוֹם {day_text} יָמִים {omer_suffix} שֶׁהֵם שָׁבוּעַ אֶחָד"

    # Days 8-49: "לעומר" comes after day count, before week breakdown
    if remaining_days == 0:
        # Exact weeks
        week_text = _hebrew_week_text(weeks)
        return f"הַיּוֹם {day_text} יוֹם {omer_suffix} שֶׁהֵם {week_text}"
    else:
        # Weeks and days
        week_text = _hebrew_week_text(weeks)
        remaining_text = _hebrew_day_text(remaining_days)
        return f"הַיּוֹם {day_text} יוֹם {omer_suffix} שֶׁהֵם {week_text} וְ{remaining_text}"


def _hebrew_week_text(weeks: int) -> str:
    """Get Hebrew text for number of weeks."""
    if weeks == 1:
        return "שָׁבוּעַ אֶחָד"
    if weeks == 2:
        return "שְׁנֵי שָׁבוּעוֹת"
    if weeks == 3:
        return "שְׁלֹשָׁה שָׁבוּעוֹת"
    if weeks == 4:
        return "אַרְבָּעָה שָׁבוּעוֹת"
    if weeks == 5:
        return "חֲמִשָּׁה שָׁבוּעוֹת"
    if weeks == 6:
        return "שִׁשָּׁה שָׁבוּעוֹת"
    if weeks == 7:
        return "שִׁבְעָה שָׁבוּעוֹת"
    return ""


def _hebrew_day_text(days: int) -> str:
    """Get Hebrew text for number of days (1-6)."""
    if days == 1:
        return "יוֹם אֶחָד"
    if days == 2:
        return "שְׁנֵי יָמִים"
    if days == 3:
        return "שְׁלֹשָׁה יָמִים"
    if days == 4:
        return "אַרְבָּעָה יָמִים"
    if days == 5:
        return "חֲמִשָּׁה יָמִים"
    if days == 6:
        return "שִׁשָּׁה יָמִים"
    return ""


def get_jerusalem_sunset(target_date: date) -> Optional[str]:
    """
    Get the tzet hakochavim (nightfall/sunset) time for Jerusalem on a given date.

    Uses jewcal's Location-based zmanim calculation for accurate sunset times.
    Returns time in Israel timezone (not UTC).

    Args:
        target_date: The Gregorian date to get sunset for

    Returns:
        Sunset time as "HH:MM" string in Israel timezone, or None if unable to calculate
    """
    try:
        # Create Jerusalem location for zmanim calculation
        location = Location(
            latitude=JERUSALEM_LAT,
            longitude=JERUSALEM_LON,
            use_tzeis_hakochavim=True,
            hadlokas_haneiros_minutes=40,  # Standard candle lighting offset
            tzeis_minutes=42  # Standard tzeis
        )

        jewcal = JewCal(gregorian_date=target_date, diaspora=False, location=location)

        if jewcal.zmanim:
            zmanim_dict = jewcal.zmanim.to_dict()
            # Try tzeis_hakochavim first (nightfall), then fall back to shkiah (sunset)
            tzeis = zmanim_dict.get('tzeis_hakochavim')
            if tzeis:
                # Parse the UTC datetime and convert to Israel timezone
                if isinstance(tzeis, str):
                    tzeis_datetime = datetime.fromisoformat(tzeis)
                    tzeis_israel = tzeis_datetime.astimezone(ISRAEL_TZ)
                    return tzeis_israel.strftime('%H:%M')
                elif hasattr(tzeis, 'astimezone'):
                    tzeis_israel = tzeis.astimezone(ISRAEL_TZ)
                    return tzeis_israel.strftime('%H:%M')
        return None
    except Exception:
        return None


def get_omer_info_for_time(
    target_date: date,
    current_hour: int,
    current_minute: int = 0
) -> dict:
    """
    Get comprehensive Omer information for display, including sunset times
    and recommended default day selection.

    Args:
        target_date: The current Gregorian date
        current_hour: Current hour (0-23)
        current_minute: Current minute (0-59)

    Returns:
        Dict with:
        - isOmerPeriod: bool
        - currentDay: int (the day being counted tonight)
        - nextDay: int (tomorrow's count)
        - defaultDay: int (recommended day to show based on time)
        - sunsetTime: str "HH:MM" (Jerusalem tzet hakochavim)
        - currentTime: str "HH:MM"
        - beforeMidnight: bool (True if before 00:00)
        - hebrewCount: str (for currentDay)
        - sefirah: str (for currentDay)
    """
    # Format current time
    current_time = f"{current_hour:02d}:{current_minute:02d}"

    # Determine if we're before midnight (for default day selection)
    before_midnight = current_hour >= 12  # After noon = "today" evening's count

    # Get the Omer day for this evening
    # If it's before midnight, we show today's count (what was/will be counted this evening)
    # If it's after midnight (00:00-06:00), we show next day's count (preparing ahead)
    after_midnight = current_hour >= 0 and current_hour < 6

    # Get sunset time for Jerusalem
    sunset_time = get_jerusalem_sunset(target_date)

    # Parse sunset time to check if we're after sunset
    sunset_hour, sunset_min = 19, 45  # default fallback
    if sunset_time:
        parts = sunset_time.split(':')
        if len(parts) == 2:
            sunset_hour, sunset_min = int(parts[0]), int(parts[1])

    current_minutes = current_hour * 60 + current_minute
    sunset_minutes = sunset_hour * 60 + sunset_min
    is_after_sunset = current_minutes >= sunset_minutes

    # Get the base Omer day for this calendar date (what would be counted tonight)
    base_omer_day = get_omer_day(target_date, after_midnight=False)

    # Get tomorrow's Omer day
    next_date = target_date + timedelta(days=1)
    next_base_omer_day = get_omer_day(next_date, after_midnight=False)

    # Get the day after tomorrow (for when we're after sunset)
    next_next_date = target_date + timedelta(days=2)
    next_next_omer_day = get_omer_day(next_next_date, after_midnight=False)

    # Determine if we're in the Omer period
    is_omer_period = base_omer_day is not None or next_base_omer_day is not None

    if not is_omer_period:
        return {
            "isOmerPeriod": False,
            "currentTime": current_time,
            "sunsetTime": sunset_time,
        }

    # Adjust current/next day based on whether we're after sunset
    # If after sunset: the "current day" becomes what was "next day"
    # and "next day" becomes the day after that
    if is_after_sunset:
        current_omer_day = next_base_omer_day
        next_omer_day = next_next_omer_day
        # Next sunset is tomorrow's sunset
        next_sunset_time = get_jerusalem_sunset(next_date)
    else:
        current_omer_day = base_omer_day
        next_omer_day = next_base_omer_day
        next_sunset_time = sunset_time  # Same day sunset

    # Calculate default day based on time:
    # - After sunset: we're counting current day NOW
    # - Before midnight (after noon, before sunset): default to current day (will count soon)
    # - After midnight (00:00-06:00): default to next day (preparing ahead)
    if is_after_sunset and current_omer_day:
        default_day = current_omer_day
    elif after_midnight and next_omer_day:
        default_day = next_omer_day
    elif current_omer_day:
        default_day = current_omer_day
    elif next_omer_day:
        default_day = next_omer_day
    else:
        default_day = 1  # Fallback

    # Get Hebrew count and sefirah for the default day
    hebrew_count = get_omer_count_text(default_day) if 1 <= default_day <= 49 else ""
    sefirah = get_sefirah_text(default_day) if 1 <= default_day <= 49 else ""

    return {
        "isOmerPeriod": True,
        "currentDay": current_omer_day,
        "nextDay": next_omer_day,
        "defaultDay": default_day,
        "sunsetTime": sunset_time,
        "nextSunsetTime": next_sunset_time,
        "currentTime": current_time,
        "beforeMidnight": before_midnight,
        "isAfterSunset": is_after_sunset,
        "hebrewCount": hebrew_count,
        "sefirah": sefirah,
    }

