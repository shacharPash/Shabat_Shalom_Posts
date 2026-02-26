"""
Shabbat/Yom Tov Poster Generator

This module generates beautiful posters with candle lighting and havdalah times
for multiple cities. It uses the jewcal library for accurate Jewish calendar
calculations and PIL for image generation.
"""

import argparse
import os
from datetime import datetime, date, timedelta
from io import BytesIO
from typing import Any, Dict, Iterable, List, Optional, Tuple

import arabic_reshaper
import pytz
import requests
from bidi.algorithm import get_display
from jewcal import JewCal
from jewcal.models.zmanim import Location
from PIL import Image, ImageDraw, ImageFont

# Import shared translation dictionaries
from translations import (
    PARASHA_TRANSLATION,
    HEBREW_MONTH_NAMES,
    YOMTOV_TRANSLATIONS,
    _PARASHA_EXACT_LOOKUP,
    _PARASHA_NORMALIZED_LOOKUP,
    _normalize_parsha_key,
    translate_parsha,
)

# Type aliases for clarity
CityDict = Dict[str, Any]
CityRow = Tuple[str, str, str]  # (city_name, candle_time, havdalah_time)
WeekInfo = Dict[str, Any]

# ========= CONFIG =========
TZID = "Asia/Jerusalem"

# Watermark configuration
WATERMARK_PATH = os.path.join(os.path.dirname(__file__), "public", "static", "watermark.png")
WATERMARK_SIZE = 60  # Width in pixels (height auto-calculated to preserve aspect ratio)
WATERMARK_MARGIN = 10  # Margin from edges in pixels
WATERMARK_OPACITY = 0.5  # 50% opacity (0.0 = invisible, 1.0 = fully opaque)

# Default cities - major Israeli cities (neutral defaults)
DEFAULT_CITIES = [
    {"name": "ירושלים", "lat": 31.779737, "lon": 35.209554, "candle_offset": 40},
    {"name": "תל אביב -יפו", "lat": 32.079112, "lon": 34.777326, "candle_offset": 20},
    {"name": "חיפה", "lat": 32.801771, "lon": 35.000609, "candle_offset": 20},
    {"name": "באר שבע", "lat": 31.256689, "lon": 34.786409, "candle_offset": 20},
]
# Keep CITIES as alias for backward compatibility
CITIES = DEFAULT_CITIES

IMG_SIZE = (1080, 1080)  # Wider rectangle (5:4 ratio)


def _convert_year_to_hebrew_letters(year: int) -> str:
    """
    Convert a Hebrew year to Hebrew letters (gematria).

    Only handles the last 2-3 digits (e.g., 5786 -> תשפ"ו).
    """
    # Hebrew letters for numbers
    ones = ["", "א", "ב", "ג", "ד", "ה", "ו", "ז", "ח", "ט"]
    tens = ["", "י", "כ", "ל", "מ", "נ", "ס", "ע", "פ", "צ"]
    hundreds = ["", "ק", "ר", "ש", "ת", "תק", "תר", "תש", "תת", "תתק"]

    # Get last 3 digits (e.g., 5786 -> 786)
    year_short = year % 1000

    h = year_short // 100
    t = (year_short % 100) // 10
    o = year_short % 10

    # Special cases for 15 and 16 (ט"ו and ט"ז instead of י"ה and י"ו)
    if t == 1 and o == 5:
        result = hundreds[h] + "ט" + "ו"
    elif t == 1 and o == 6:
        result = hundreds[h] + "ט" + "ז"
    else:
        result = hundreds[h] + tens[t] + ones[o]

    # Add quotation mark before last letter
    if len(result) > 1:
        result = result[:-1] + '"' + result[-1]
    elif len(result) == 1:
        result = result + "'"

    return result


def get_hebrew_date_string(gregorian_date: date) -> str:
    """
    Get the Hebrew date string for a given Gregorian date.

    Args:
        gregorian_date: The Gregorian date to convert

    Returns:
        Hebrew date string like "כ״ג כסלו תשפ״ו"
    """
    jc = JewCal(gregorian_date=gregorian_date, diaspora=False)
    jewish_date = jc.jewish_date

    # Get day, month name, and year
    day = jewish_date.day
    year = jewish_date.year

    # Get month name from the string representation (e.g., "23 Kislev 5786")
    date_str = str(jewish_date)
    parts = date_str.split()
    if len(parts) >= 2:
        month_name_english = parts[1]
        month_name = HEBREW_MONTH_NAMES.get(month_name_english, month_name_english)
    else:
        month_name = ""

    # Convert day to Hebrew letters
    day_hebrew = _convert_day_to_hebrew(day)

    # Convert year to Hebrew letters
    year_hebrew = _convert_year_to_hebrew_letters(year)

    return f"{day_hebrew} {month_name} {year_hebrew}"


def _convert_day_to_hebrew(day: int) -> str:
    """Convert a day number (1-30) to Hebrew gematria with geresh/gershayim."""
    ones = ["", "א", "ב", "ג", "ד", "ה", "ו", "ז", "ח", "ט"]
    tens = ["", "י", "כ", "ל"]

    t = day // 10
    o = day % 10

    # Special cases for 15 and 16
    if day == 15:
        return 'ט"ו'
    elif day == 16:
        return 'ט"ז'

    if t == 0:
        return ones[o] + "'"
    elif o == 0:
        return tens[t] + "'"
    else:
        return tens[t] + '"' + ones[o]

# ========= TEXT HELPERS =========
def fix_hebrew(text: str) -> str:
    """Convert Hebrew text to proper RTL display format."""
    if not text:
        return text
    return get_display(arabic_reshaper.reshape(text))


# Font cache to avoid reloading fonts repeatedly
# Cache stores: (size, bold) -> (font, is_bold)
_font_cache: dict[tuple[int, bool], tuple[ImageFont.FreeTypeFont, bool]] = {}

# Font file candidates (searched in order)
_FONT_CANDIDATES_BOLD = ["Alef-Bold.ttf", "Alef-Regular.ttf", "DejaVuSans.ttf"]
_FONT_CANDIDATES_REGULAR = ["Alef-Regular.ttf", "DejaVuSans.ttf"]


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """
    Load a font with caching for performance.

    Args:
        size: Font size in points
        bold: Whether to use bold variant

    Returns:
        Loaded font object (with _is_bold attribute set)
    """
    cache_key = (size, bold)

    # Return cached font if available
    if cache_key in _font_cache:
        font, _ = _font_cache[cache_key]
        return font

    candidates = _FONT_CANDIDATES_BOLD if bold else _FONT_CANDIDATES_REGULAR

    for path in candidates:
        if os.path.isfile(path):
            try:
                font = ImageFont.truetype(path, size=size)
                # Store font with its bold state
                font._is_bold = bold  # type: ignore
                _font_cache[cache_key] = (font, bold)
                return font
            except Exception:
                continue

    # Fall back to default font (not cached as it's a different type)
    default_font = ImageFont.load_default()
    default_font._is_bold = False  # type: ignore
    return default_font



# ========= DATA FROM JEWCAL =========
def find_event_sequence(start_date: date) -> tuple[date, date, str, str]:
    """Find a complete event sequence (Shabbat or holiday sequence).
    Returns: (start_date, end_date, event_type, event_name)
    """
    from jewcal import JewCal

    current_date = start_date
    sequence_start = start_date
    sequence_end = start_date
    main_event_type = None
    main_event_name = None

    # Find the start of the sequence (if we're in the middle)
    # Only go back if the previous day is part of a continuous sequence
    while True:
        prev_day = current_date - timedelta(days=1)
        prev_jewcal = JewCal(gregorian_date=prev_day, diaspora=False)

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
        jewcal = JewCal(gregorian_date=current_date, diaspora=False)

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
            next_jewcal = JewCal(gregorian_date=next_day, diaspora=False)

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
    next_jewcal = JewCal(gregorian_date=next_day, diaspora=False)

    # If next day has events that require candle lighting, current day is not the end
    if (next_jewcal.has_events() and
        next_jewcal.events.action in ["Candles", "Havdalah"]):
        return False

    return True


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

    # Create location object
    location = Location(
        latitude=lat,
        longitude=lon,
        use_tzeis_hakochavim=True,
        hadlokas_haneiros_minutes=candle_offset,
        tzeis_minutes=42
    )

    # Get candle lighting time from the start of the sequence
    start_jewcal = JewCal(gregorian_date=start_date, diaspora=False, location=location)
    candle_time = None
    if start_jewcal.zmanim:
        start_zmanim = start_jewcal.zmanim.to_dict()
        if start_zmanim.get('hadlokas_haneiros'):
            candle_time = start_zmanim['hadlokas_haneiros']

    # Get havdalah time from the end of the sequence
    end_jewcal = JewCal(gregorian_date=end_date, diaspora=False, location=location)
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

def jewcal_times_for_date(lat: float, lon: float, target_date: date, candle_offset: int) -> dict:
    """Calculate Shabbat/Yom Tov times using jewcal library for accurate local calculations."""

    # Create location object
    location = Location(
        latitude=lat,
        longitude=lon,
        use_tzeis_hakochavim=True,  # Use stars for havdalah calculation
        hadlokas_haneiros_minutes=candle_offset,  # Custom candle lighting offset
        tzeis_minutes=42  # 42 minutes after sunset for havdalah (backup)
    )

    # Get JewCal info for the target date (Israel customs since we're in Israel)
    jewcal = JewCal(gregorian_date=target_date, diaspora=False, location=location)

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

# ========= HEBCAL API INTEGRATION =========
# Hebcal API functions have been extracted to hebcal_api.py module
from hebcal_api import get_parsha_from_hebcal, clear_hebcal_cache, _get_saturday_for_date

# Israel timezone constant for time conversions
_ISRAEL_TZ = pytz.timezone('Asia/Jerusalem')


def iso_to_hhmm(iso_str: Optional[str]) -> str:
    """
    Convert an ISO datetime string to HH:MM format in Israel timezone.

    Args:
        iso_str: ISO 8601 datetime string (e.g., "2025-01-24T16:30:00+02:00")

    Returns:
        Time in HH:MM format, or "--:--" if input is empty/None
    """
    if not iso_str:
        return "--:--"

    try:
        # Parse the datetime string
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))

        if dt.tzinfo is None:
            # If no timezone info, assume UTC
            dt = pytz.utc.localize(dt)

        # Convert to Israel time
        israel_time = dt.astimezone(_ISRAEL_TZ)
        return israel_time.strftime("%H:%M")
    except (ValueError, AttributeError):
        return "--:--"


# ========= IMAGE HELPERS =========
# EXIF orientation tag and rotation values
_EXIF_ORIENTATION_TAG = 274
_ORIENTATION_ROTATIONS = {
    3: 180,
    6: 270,
    8: 90,
}


def fix_image_orientation(img: Image.Image) -> Image.Image:
    """
    Fix image orientation based on EXIF data.

    Many cameras store images in a default orientation and use EXIF metadata
    to indicate how the image should be rotated for display.

    Args:
        img: PIL Image object

    Returns:
        Image rotated to correct orientation
    """
    try:
        exif = img._getexif()
        if exif is not None:
            orientation = exif.get(_EXIF_ORIENTATION_TAG)
            rotation = _ORIENTATION_ROTATIONS.get(orientation)
            if rotation:
                img = img.rotate(rotation, expand=True)
    except (AttributeError, KeyError, TypeError):
        pass
    return img


def fit_background(
    image_path: str,
    size: Tuple[int, int] = (1080, 1080),
    crop_position: Optional[Tuple[float, float]] = None
) -> Image.Image:
    """
    Load and resize an image to fill the target size with customizable crop position.

    Args:
        image_path: Path to the image file
        size: Target size as (width, height)
        crop_position: Tuple of (x, y) as percentages (0.0 to 1.0) where
                       (0.5, 0.5) is center, (0.0, 0.0) is top-left,
                       (1.0, 1.0) is bottom-right. Default is center.

    Returns:
        Resized and cropped PIL Image
    """
    base_w, base_h = size
    img = Image.open(image_path).convert("RGB")

    # Fix orientation based on EXIF data
    img = fix_image_orientation(img)

    # Scale to cover the target size
    scale = max(base_w / img.width, base_h / img.height)
    new_w = int(img.width * scale)
    new_h = int(img.height * scale)
    img = img.resize((new_w, new_h), Image.LANCZOS)

    # Use provided crop position or default to center (0.5, 0.5)
    crop_x, crop_y = crop_position if crop_position else (0.5, 0.5)

    # Clamp values to valid range [0.0, 1.0]
    crop_x = max(0.0, min(1.0, crop_x))
    crop_y = max(0.0, min(1.0, crop_y))

    # Calculate crop position based on percentage
    # The crop window can move from 0 to (new_dimension - base_dimension)
    max_left = new_w - base_w
    max_top = new_h - base_h

    left = int(max_left * crop_x)
    top = int(max_top * crop_y)

    img = img.crop((left, top, left + base_w, top + base_h))
    return img


def get_text_width(text: str, font: ImageFont.FreeTypeFont, rtl: bool = False) -> int:
    """
    Get the width of text rendered with the given font.

    Args:
        text: Text to measure
        font: Font to use
        rtl: Whether to apply RTL text processing

    Returns:
        Width in pixels
    """
    if rtl:
        text = fix_hebrew(text)
    bbox = font.getbbox(text)
    return bbox[2] - bbox[0]


def get_fitted_font(
    text: str,
    original_font: ImageFont.FreeTypeFont,
    max_width: int,
    rtl: bool = False,
    min_size: int = 20
) -> ImageFont.FreeTypeFont:
    """
    Get a font that fits the text within max_width.

    Iteratively reduces font size until text fits or min_size is reached.

    Args:
        text: Text to fit
        original_font: Starting font
        max_width: Maximum allowed width in pixels
        rtl: Whether to apply RTL text processing
        min_size: Minimum font size to use

    Returns:
        Font that fits the text (or min_size font if nothing fits)
    """
    current_size = original_font.size
    is_bold = getattr(original_font, '_is_bold', False)

    # Check if original font fits
    if get_text_width(text, original_font, rtl) <= max_width:
        return original_font

    # Find the largest font size that fits
    while current_size > min_size:
        current_size -= 2
        test_font = load_font(current_size, bold=is_bold)
        if get_text_width(text, test_font, rtl) <= max_width:
            return test_font

    # Return minimum size font if nothing fits
    return load_font(min_size, bold=is_bold)

def draw_text_with_stroke(draw, xy, text, font, fill, stroke_fill, stroke_width, anchor=None, rtl=False):
    if rtl:
        text = fix_hebrew(text)
    draw.text(
        xy, text, font=font, fill=fill,
        stroke_width=stroke_width, stroke_fill=stroke_fill,
        anchor=anchor
    )


def overlay_watermark(
    img: Image.Image,
    watermark_path: str = WATERMARK_PATH,
    size: int = WATERMARK_SIZE,
    margin: int = WATERMARK_MARGIN,
    opacity: float = WATERMARK_OPACITY,
) -> Image.Image:
    """
    Overlay a watermark image on the bottom-right corner of the poster.

    Args:
        img: The poster image to add watermark to
        watermark_path: Path to the watermark image file
        size: Target width for the watermark (height auto-calculated)
        margin: Margin from the edges in pixels
        opacity: Opacity level (0.0 to 1.0)

    Returns:
        Image with watermark overlaid
    """
    if not os.path.isfile(watermark_path):
        # Watermark file not found, return original image
        return img

    try:
        # Load watermark image with transparency support
        watermark = Image.open(watermark_path).convert("RGBA")

        # Calculate new height maintaining aspect ratio
        aspect_ratio = watermark.height / watermark.width
        new_width = size
        new_height = int(size * aspect_ratio)

        # Resize watermark
        watermark = watermark.resize((new_width, new_height), Image.LANCZOS)

        # Apply opacity to the watermark
        if opacity < 1.0:
            # Split into channels and adjust alpha
            r, g, b, a = watermark.split()
            a = a.point(lambda x: int(x * opacity))
            watermark = Image.merge("RGBA", (r, g, b, a))

        # Calculate position (bottom-right with margin)
        W, H = img.size
        x = W - new_width - margin
        y = H - new_height - margin

        # Ensure img is in RGBA mode for compositing
        if img.mode != "RGBA":
            img = img.convert("RGBA")

        # Create a copy and paste watermark with transparency
        result = img.copy()
        result.paste(watermark, (x, y), watermark)

        # Convert back to RGB if original was RGB
        return result.convert("RGB")

    except Exception as e:
        # If anything goes wrong, return original image
        print(f"Warning: Could not overlay watermark: {e}")
        return img


# ========= COMPOSER =========
def compose_poster(
    bg_img: Image.Image,
    week_info: dict,
    all_cities_rows: list,
    blessing_text: str | None = None,
    dedication_text: str | None = None,
    date_format: str = "gregorian",  # "gregorian", "hebrew", or "both"
    show_watermark: bool = True,  # Enable/disable watermark
) -> Image.Image:
    img = bg_img.copy()
    W, H = img.size
    draw = ImageDraw.Draw(img)

    title_font = load_font(100, bold=True)
    sub_font   = load_font(54)
    bless_font = load_font(60, bold=True)
    small_font = load_font(36)

    stroke_w = 5
    fill = "white"
    stroke = "black"

    # Determine title based on event type
    event_info = week_info.get("event_info", {})
    event_type = event_info.get("event_type", "shabbos")
    event_name = event_info.get("event_name", "")

    if event_type == "yomtov":
        # For Yom Tov, use the event name or a generic greeting
        if "Rosh Hashana" in event_name:
            title = "שנה טובה"
        elif "Yom Kippur" in event_name:
            title = "גמר חתימה טובה"
        elif "Sukkos" in event_name or "Sukkot" in event_name:
            title = "חג שמח"
        elif "Pesach" in event_name:
            title = "חג כשר ושמח"
        elif "Shavuos" in event_name or "Shavut" in event_name:
            title = "חג שמח"
        else:
            title = "חג שמח"  # Generic holiday greeting
    else:
        title = "שבת שלום"  # Shabbat greeting

    # Apply main title override if provided
    if week_info.get("main_title_override"):
        title = week_info["main_title_override"]

    # התאמת גודל פונט לכותרת הראשית
    fitted_title_font = get_fitted_font(title, title_font, W - 100, rtl=True)
    draw_text_with_stroke(draw, (W//2, 40), title, fitted_title_font, fill, stroke, stroke_w, anchor="ma", rtl=True)

    # Create subtitle with parsha and date range
    parsha_txt = week_info.get("parsha") or ""
    seq_start = week_info.get("seq_start")
    seq_end = week_info.get("seq_end")

    # Build date string based on date_format parameter
    date_str = ""
    if seq_start and seq_end:
        # Gregorian date formatting
        if date_format in ("gregorian", "both"):
            if seq_start == seq_end:
                greg_str = seq_start.strftime("%d.%m.%Y")
            else:
                if seq_start.month == seq_end.month and seq_start.year == seq_end.year:
                    greg_str = f"{seq_start.day}-{seq_end.day}.{seq_end.month:02d}.{seq_end.year}"
                else:
                    greg_str = f"{seq_start.strftime('%d.%m')}-{seq_end.strftime('%d.%m.%Y')}"
            date_str = greg_str

        # Hebrew date formatting
        if date_format in ("hebrew", "both"):
            heb_start = get_hebrew_date_string(seq_start)
            if seq_start == seq_end:
                heb_str = heb_start
            else:
                heb_end = get_hebrew_date_string(seq_end)
                # If same month, just show day range
                heb_start_parts = heb_start.split()
                heb_end_parts = heb_end.split()
                if len(heb_start_parts) >= 3 and len(heb_end_parts) >= 3:
                    if heb_start_parts[1] == heb_end_parts[1]:  # Same month
                        heb_str = f"{heb_start_parts[0]}-{heb_end_parts[0]} {heb_end_parts[1]} {heb_end_parts[2]}"
                    else:
                        heb_str = f"{heb_start} - {heb_end}"
                else:
                    heb_str = f"{heb_start} - {heb_end}"

            if date_format == "both" and date_str:
                date_str = f"{date_str} | {heb_str}"
            else:
                date_str = heb_str

    # Add event name for Yom Tov
    if event_type == "yomtov" and event_name:
        # Translate common Yom Tov names to Hebrew
        hebrew_event = YOMTOV_TRANSLATIONS.get(event_name, event_name)
        if parsha_txt:
            sub_line = f"{hebrew_event} | {parsha_txt} | {date_str}"
        else:
            sub_line = f"{hebrew_event} | {date_str}"
    else:
        sub_line = f"{parsha_txt} | {date_str}" if parsha_txt else date_str

    # Apply subtitle override if provided (replaces entire subtitle line)
    if week_info.get("subtitle_override"):
        sub_line = week_info["subtitle_override"]

    # התאמת גודל פונט לכותרת המשנה
    fitted_sub_font = get_fitted_font(sub_line, sub_font, W - 100, rtl=True)
    draw_text_with_stroke(draw, (W//2, 140), sub_line, fitted_sub_font, fill, stroke, stroke_w, anchor="ma", rtl=True)

    # Adjust font size and spacing based on number of cities
    num_cities = len(all_cities_rows)
    if num_cities <= 4:
        # Standard sizing for 4 or fewer cities
        city_font_size = 50
        row_spacing = 10
    elif num_cities <= 6:
        # Medium sizing for 5-6 cities
        city_font_size = 42
        row_spacing = 6
    else:
        # Compact sizing for 7-8 cities
        city_font_size = 36
        row_spacing = 4

    city_row_font = load_font(city_font_size)

    # Calculate table dimensions
    table_height = (num_cities + 1) * (city_font_size + row_spacing) + 40
    table_width = W - 200  # רוחב קטן יותר

    # Determine text content and layout
    # No defaults - if None or empty, don't show anything
    if blessing_text is None:
        blessing_text = ""
    if dedication_text is None:
        dedication_text = ""

    # Position table dynamically based on what text is shown
    # Calculate bottom section based on what's visible
    show_blessing = bool(blessing_text)
    show_dedication = bool(dedication_text)

    if show_blessing and show_dedication:
        # Normal layout with both blessing and dedication
        blessing_y = H - 125
        dedication_y = H - 50
        table_bottom_ref = blessing_y
    elif show_blessing and not show_dedication:
        # Only blessing, no dedication
        blessing_y = H - 85
        table_bottom_ref = blessing_y
    elif not show_blessing and show_dedication:
        # Only dedication, no blessing
        dedication_y = H - 50
        table_bottom_ref = H - 85  # Table comes closer to bottom
    else:
        # Neither blessing nor dedication
        table_bottom_ref = H - 40  # Table very close to bottom

    table_to_blessing_gap = 10  # Consistent gap between table bottom and text
    table_top = table_bottom_ref - table_to_blessing_gap - table_height

    # יצירת רקע עגול קטן יותר
    overlay = Image.new("RGBA", (table_width, table_height), (0,0,0,0))
    overlay_draw = ImageDraw.Draw(overlay)

    # ציור ריבוע עגול עם פינות מעוגלות - קטן יותר
    corner_radius = 25
    overlay_draw.rounded_rectangle(
        [0, 0, table_width, table_height],
        radius=corner_radius,
        fill=(0, 0, 0, 70)
    )

    # מרכוז הטבלה אופקית
    table_left = (W - table_width) // 2
    img.paste(overlay, (table_left, table_top), overlay)

    draw = ImageDraw.Draw(img)
    # פיזור אחיד של העמודות בתוך הריבוע השחור עם רווחים שווים מכל הצדדים
    margin = 40  # רווח אחיד מקצוות הריבוע השחור
    usable_width = table_width - (2 * margin)  # רוחב זמין לטקסט
    col_spacing = usable_width // 4  # חלוקה ל-4 חלקים שווים

    col_hav_x    = table_left + margin + col_spacing * 0.5    # זמן יציאה - שמאל
    col_candle_x = table_left + margin + col_spacing * 2      # זמן כניסה - אמצע
    col_city_x   = table_left + margin + col_spacing * 3.5    # עיר - ימין
    y = table_top + 30

    # Update column headers based on event type
    event_info = week_info.get("event_info", {})
    event_type = event_info.get("event_type", "shabbos")

    # כותרות עמודות - ממורכזות (use same font as rows for consistency)
    draw_text_with_stroke(draw, (col_city_x, y), "עיר", city_row_font, fill, stroke, stroke_w, anchor="ma", rtl=True)

    if event_type == "yomtov":
        draw_text_with_stroke(draw, (col_candle_x, y), "הדלקת נרות", city_row_font, fill, stroke, stroke_w, anchor="ma", rtl=True)
        draw_text_with_stroke(draw, (col_hav_x, y), "צאת החג", city_row_font, fill, stroke, stroke_w, anchor="ma", rtl=True)
    else:
        draw_text_with_stroke(draw, (col_candle_x, y), "כניסת שבת", city_row_font, fill, stroke, stroke_w, anchor="ma", rtl=True)
        draw_text_with_stroke(draw, (col_hav_x, y), "צאת שבת", city_row_font, fill, stroke, stroke_w, anchor="ma", rtl=True)
    y += city_font_size + row_spacing

    for name, candle_hhmm, hav_hhmm in all_cities_rows:
        # נתונים ממורכזים בכל עמודה
        draw_text_with_stroke(draw, (col_city_x, y), name, city_row_font, fill, stroke, stroke_w, anchor="ma", rtl=True)
        draw_text_with_stroke(draw, (col_candle_x, y), candle_hhmm, city_row_font, fill, stroke, stroke_w, anchor="ma")
        draw_text_with_stroke(draw, (col_hav_x, y), hav_hhmm, city_row_font, fill, stroke, stroke_w, anchor="ma")
        y += city_font_size + row_spacing - 2

    # Only draw blessing text if it's shown
    if show_blessing:
        draw_text_with_stroke(
            draw, (W//2, blessing_y),
            blessing_text, bless_font,
            fill, stroke, stroke_w,
            anchor="ma", rtl=True,
        )
    # Only draw dedication text if it's shown
    if show_dedication:
        draw_text_with_stroke(
            draw, (W//2, dedication_y),
            dedication_text, small_font,
            fill, stroke, 3,
            anchor="ma", rtl=True,
        )

    # Add watermark if enabled
    if show_watermark:
        img = overlay_watermark(img)

    # Do NOT save to disk here anymore
    return img

# ========= MAIN =========
def next_friday(d: date) -> date:
    days_ahead = (4 - d.weekday()) % 7
    if days_ahead == 0 and datetime.now().hour >= 12:
        days_ahead = 7
    return d + timedelta(days=days_ahead)

def find_next_sequence(start_base: date) -> tuple[date, date, str, str]:
    """Find the next event sequence starting from start_base.
    Returns: (start_date, end_date, event_type, event_name)
    """
    current_date = start_base

    # Check up to 14 days ahead to find the next event
    for i in range(14):
        check_date = current_date + timedelta(days=i)

        # Create a temporary jewcal object to check for events
        temp_jewcal = JewCal(gregorian_date=check_date, diaspora=False)

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
        temp_jewcal = JewCal(gregorian_date=check_date, diaspora=False)

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


def generate_poster(
    *,
    image_path: str,
    start_date: Optional[date] = None,
    cities: Optional[Iterable[CityDict]] = None,
    blessing_text: Optional[str] = None,
    dedication_text: Optional[str] = None,
    date_format: str = "gregorian",  # "gregorian", "hebrew", or "both"
    overrides: Optional[Dict[str, str]] = None,  # Manual overrides for poster fields
    crop_position: Optional[Tuple[float, float]] = None,  # Image crop position (x, y) as 0.0-1.0
    show_watermark: bool = True,  # Enable/disable watermark
) -> bytes:
    """
    Generate a single Shabbat/Yom Tov poster for one background image.

    This is the main entry point for poster generation. It finds the next
    Shabbat or holiday sequence, calculates candle lighting and havdalah
    times for each city, and renders a beautiful poster image.

    Args:
        image_path: Path to the background image file
        start_date: Base date to search from (default: today)
        cities: List of city dicts with keys: name, lat, lon, candle_offset
        blessing_text: Custom bottom message (default: standard blessing)
        dedication_text: Custom 'leiluy neshama' text (default: None)
        date_format: Date format - "gregorian", "hebrew", or "both"
        overrides: Optional dict with manual overrides:
            - main_title: Custom main title (e.g., "שבת שלום")
            - subtitle: Custom subtitle (entire line with parsha + date)
            - custom_cities: List of custom cities with manual times
              [{ "name": "...", "candle": "HH:MM", "havdalah": "HH:MM" }]
        crop_position: Tuple of (x, y) as percentages (0.0 to 1.0) for crop position.
                       (0.5, 0.5) is center (default), (0.0, 0.0) is top-left.
        show_watermark: Whether to show the watermark on the poster (default: True)

    Returns:
        PNG image bytes ready to be saved or transmitted
    """
    # Use defaults if not provided
    if start_date is None:
        start_date = date.today()
    if cities is None:
        cities = DEFAULT_CITIES  # Use neutral default cities

    # Find the next event sequence (ignore event_type and event_name here,
    # as they're obtained from jewcal_times_for_sequence for each city)
    seq_start, seq_end, _, _ = find_next_sequence(start_date)

    # Compute parsha and zmanim for all cities
    rows: List[CityRow] = []
    parsha_name: Optional[str] = None
    event_info: Optional[Dict[str, Any]] = None

    for city in cities:
        info = jewcal_times_for_sequence(
            city["lat"], city["lon"], seq_start, seq_end, city["candle_offset"]
        )
        if not parsha_name and info.get("parsha"):
            parsha_name = info["parsha"]
        if not event_info:
            event_info = {
                "event_name": info.get("event_name"),
                "event_type": info.get("event_type"),
                "action": info.get("action"),
            }
        candle_hhmm = iso_to_hhmm(info.get("candle"))
        hav_hhmm = iso_to_hhmm(info.get("havdalah"))
        rows.append((city["name"], candle_hhmm, hav_hhmm))

    # Add custom cities with manual times (if provided)
    custom_cities = overrides.get("custom_cities") if overrides else None
    if custom_cities:
        for custom in custom_cities:
            name = custom.get("name", "")
            candle = custom.get("candle", "")
            havdalah = custom.get("havdalah", "")
            if name:
                rows.append((name, candle, havdalah))

    # If no predefined cities were processed (only custom cities),
    # we still need event_info and parsha for the poster header.
    # Use Jerusalem coordinates as reference point.
    if not event_info:
        # Jerusalem coordinates
        ref_lat, ref_lon = 31.779737, 35.209554
        ref_info = jewcal_times_for_sequence(ref_lat, ref_lon, seq_start, seq_end, 40)
        parsha_name = ref_info.get("parsha")
        event_info = {
            "event_name": ref_info.get("event_name"),
            "event_type": ref_info.get("event_type"),
            "action": ref_info.get("action"),
        }

    # Create background image with custom crop position
    bg = fit_background(image_path, IMG_SIZE, crop_position=crop_position)

    # Build week info
    week_info = {
        "parsha": parsha_name,
        "seq_start": seq_start,
        "seq_end": seq_end,
        "event_info": event_info,
    }

    # Apply title overrides if provided
    if overrides:
        if overrides.get("main_title"):
            week_info["main_title_override"] = overrides["main_title"]
        if overrides.get("subtitle"):
            week_info["subtitle_override"] = overrides["subtitle"]

    # Compose the poster image
    img = compose_poster(
        bg, week_info, rows,
        blessing_text=blessing_text,
        dedication_text=dedication_text,
        date_format=date_format,
        show_watermark=show_watermark,
    )

    # Save to BytesIO buffer as PNG and return bytes
    buffer = BytesIO()
    img.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def main():
    parser = argparse.ArgumentParser(description="Generate Shabbat/Yom Tov posts with candle times")
    parser.add_argument("--images-dir", default="images", help="Input images folder")
    parser.add_argument("--start-date", default=None, help="YYYY-MM-DD, default is today -> next event")
    args = parser.parse_args()

    if args.start_date:
        start_base = date.fromisoformat(args.start_date)
    else:
        start_base = date.today()

    # Find event sequences instead of individual events
    exts = {".jpg", ".jpeg", ".png", ".webp"}
    images = [os.path.join(args.images_dir, f) for f in sorted(os.listdir(args.images_dir))]
    images = [p for p in images if os.path.splitext(p)[1].lower() in exts]
    if not images:
        raise SystemExit("No images found in input folder.")

    current_search_date = start_base
    processed_sequences = []  # Track which sequences we've already processed

    for img_path in images:
        # Find the next sequence (for naming the file and updating search date)
        seq_start, seq_end, event_type, _ = find_next_sequence(current_search_date)

        # Skip if we've already processed this sequence
        if any(seq_start <= existing_end and seq_end >= existing_start
               for existing_start, existing_end in processed_sequences):
            # Move search date past this sequence
            current_search_date = seq_end + timedelta(days=1)
            seq_start, seq_end, event_type, _ = find_next_sequence(current_search_date)

        processed_sequences.append((seq_start, seq_end))

        # Generate the poster using the reusable function
        poster_bytes = generate_poster(
            image_path=img_path,
            start_date=current_search_date,
            # blessing_text and dedication_text left as defaults
        )

        # Create filename based on event type and sequence
        event_type_str = event_type or "shabbos"
        if seq_start == seq_end:
            out_name = f"output/{event_type_str}_{seq_start.isoformat()}_cities.png"
        else:
            out_name = f"output/{event_type_str}_{seq_start.isoformat()}_to_{seq_end.isoformat()}_cities.png"

        # Save the poster bytes to disk
        os.makedirs(os.path.dirname(out_name), exist_ok=True)
        with open(out_name, "wb") as f:
            f.write(poster_bytes)
        print(f"Generated file: {out_name}")

        # Move to next sequence
        current_search_date = seq_end + timedelta(days=1)


if __name__ == "__main__":
    main()
