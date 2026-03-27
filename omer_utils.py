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

from datetime import date, timedelta
from functools import lru_cache
from typing import Optional

from jewcal import JewCal

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


def get_omer_count_text(day: int) -> str:
    """
    Get the full Hebrew counting text for a given Omer day.

    Args:
        day: The Omer day (1-49)

    Returns:
        The full Hebrew counting text (e.g., "הַיּוֹם יוֹם אֶחָד לָעֹמֶר")
    """
    if day < 1 or day > 49:
        raise ValueError(f"Omer day must be 1-49, got {day}")

    # Handle weeks and days
    weeks = day // 7
    remaining_days = day % 7

    # Build the count text
    day_text = _hebrew_number(day)

    if day == 1:
        return f"הַיּוֹם יוֹם {day_text} לָעֹמֶר"

    # Days 2-6: "היום X ימים לעומר"
    if day < 7:
        return f"הַיּוֹם {day_text} יָמִים לָעֹמֶר"

    # Day 7: "היום שבעה ימים שהם שבוע אחד לעומר"
    if day == 7:
        return f"הַיּוֹם {day_text} יָמִים שֶׁהֵם שָׁבוּעַ אֶחָד לָעֹמֶר"

    # Days 8-49: Include weeks
    if remaining_days == 0:
        # Exact weeks
        week_text = _hebrew_week_text(weeks)
        return f"הַיּוֹם {day_text} יוֹם שֶׁהֵם {week_text} לָעֹמֶר"
    else:
        # Weeks and days
        week_text = _hebrew_week_text(weeks)
        remaining_text = _hebrew_day_text(remaining_days)
        return f"הַיּוֹם {day_text} יוֹם שֶׁהֵם {week_text} וְ{remaining_text} לָעֹמֶר"


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

