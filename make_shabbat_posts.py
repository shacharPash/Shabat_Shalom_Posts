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

# Import Omer utilities
from omer_utils import get_omer_day, get_omer_count_text, get_sefirah_text

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

# Import calendar utility functions
from calendar_utils import (
    find_event_sequence,
    find_next_event_date,
    find_next_sequence,
    is_end_of_holiday_sequence,
    jewcal_times_for_date,
    jewcal_times_for_sequence,
    next_friday,
)

# Import image utility functions
from image_utils import (
    _fit_background_fixed,
    _fit_background_flexible,
    assemble_gif,
    draw_text_with_stroke,
    extract_gif_frames,
    extract_video_frames,
    fit_background,
    fix_hebrew,
    fix_image_orientation,
    get_fitted_font,
    get_text_width,
    is_animated_gif,
    is_video_file,
    load_font,
    overlay_watermark,
)

# Type aliases for clarity
CityDict = Dict[str, Any]
CityRow = Tuple[str, str, str]  # (city_name, candle_time, havdalah_time)
WeekInfo = Dict[str, Any]

# ========= CONFIG =========
TZID = "Asia/Jerusalem"

# Watermark configuration
def _find_watermark_path():
    """Find watermark file in possible locations."""
    possible_paths = [
        # Vercel serverless - watermark in api folder (highest priority)
        os.path.join(os.path.dirname(__file__), "api", "watermark.png"),
        # Local development - public folder
        os.path.join(os.path.dirname(__file__), "public", "static", "watermark.png"),
        # Relative paths
        "api/watermark.png",
        "public/static/watermark.png",
    ]
    for path in possible_paths:
        if os.path.isfile(path):
            return path
    return possible_paths[0]  # Return first as fallback


WATERMARK_PATH = _find_watermark_path()
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

IMG_SIZE = (1080, 1080)  # Default size (used when aspect_ratio="1:1")

# Aspect ratio presets
ASPECT_RATIO_SIZES = {
    "1:1": (1080, 1080),   # Square (Instagram post)
    "4:5": (1080, 1350),   # Portrait (Instagram feed optimal)
    "auto": None,          # Use flexible aspect ratio based on original image
}


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




# ========= DATA FROM JEWCAL =========

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


def wrap_hebrew_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """
    Wrap Hebrew text to fit within max_width.

    Splits on spaces and builds lines that fit within the maximum width.

    Args:
        text: Hebrew text to wrap
        font: Font to use for measuring
        max_width: Maximum width in pixels for each line

    Returns:
        List of lines that fit within max_width
    """
    words = text.split()
    lines = []
    current_line = []

    for word in words:
        # Try adding the word to the current line
        test_line = " ".join(current_line + [word])
        if get_text_width(test_line, font, rtl=True) <= max_width:
            current_line.append(word)
        else:
            # Current word doesn't fit, save current line and start new one
            if current_line:
                lines.append(" ".join(current_line))
            current_line = [word]

    # Add the last line
    if current_line:
        lines.append(" ".join(current_line))

    return lines


def draw_multiline_text_with_stroke(
    draw: ImageDraw.Draw,
    xy: tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: str,
    stroke_fill: str,
    stroke_width: int,
    max_width: int,
    line_spacing: int = 10,
    anchor: str = "ma",
    rtl: bool = True
) -> int:
    """
    Draw multi-line text centered with stroke, wrapping to fit max_width.

    Args:
        draw: PIL ImageDraw object
        xy: Position tuple (x, y) for first line
        text: Text to draw
        font: Font to use
        fill: Text fill color
        stroke_fill: Stroke color
        stroke_width: Width of the stroke
        max_width: Maximum width for text wrapping
        line_spacing: Extra spacing between lines
        anchor: Text anchor position
        rtl: Whether to apply RTL text processing

    Returns:
        Total height used by all lines (for positioning subsequent content)
    """
    lines = wrap_hebrew_text(text, font, max_width)
    x, y = xy

    # Calculate line height
    bbox = font.getbbox("אבגדהוזחט")  # Sample Hebrew text
    line_height = bbox[3] - bbox[1] + line_spacing

    for line in lines:
        draw_text_with_stroke(draw, (x, y), line, font, fill, stroke_fill, stroke_width, anchor=anchor, rtl=rtl)
        y += line_height

    return len(lines) * line_height


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
    draw_text_with_stroke(draw, (W//2, 145), sub_line, fitted_sub_font, fill, stroke, stroke_w, anchor="ma", rtl=True)

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
        img = overlay_watermark(
            img,
            watermark_path=WATERMARK_PATH,
            size=WATERMARK_SIZE,
            margin=WATERMARK_MARGIN,
            opacity=WATERMARK_OPACITY
        )

    # Do NOT save to disk here anymore
    return img


def compose_omer_poster(
    bg_img: Image.Image,
    omer_day: int,
    omer_date: date,
    blessing_text: str | None = None,
    dedication_text: str | None = None,
    date_format: str = "both",
    show_watermark: bool = True,
) -> Image.Image:
    """
    Compose a Sefirat HaOmer poster with blessing, count, and Harachaman text.

    Args:
        bg_img: Background image
        omer_day: The Omer day (1-49)
        omer_date: The date for the Omer poster (for subtitle date display)
        blessing_text: Custom bottom message (optional)
        dedication_text: Custom dedication text (optional)
        date_format: Date format for subtitle - "gregorian", "hebrew", or "both"
        show_watermark: Whether to show watermark

    Returns:
        Composed poster image
    """
    img = bg_img.copy()
    W, H = img.size
    draw = ImageDraw.Draw(img)

    title_font = load_font(100, bold=True)
    sub_font = load_font(54)
    bless_font = load_font(60, bold=True)
    small_font = load_font(36)

    stroke_w = 5
    fill = "white"
    stroke = "black"

    # Title: ספירת העומר
    title = "ספירת העומר"
    fitted_title_font = get_fitted_font(title, title_font, W - 100, rtl=True)
    draw_text_with_stroke(draw, (W//2, 40), title, fitted_title_font, fill, stroke, stroke_w, anchor="ma", rtl=True)

    # Subtitle: Hebrew date | Gregorian date | Sefirah
    sefirah_text = get_sefirah_text(omer_day)

    # Build date string based on date_format parameter
    date_parts = []
    if date_format in ("hebrew", "both"):
        hebrew_date = get_hebrew_date_string(omer_date)
        date_parts.append(hebrew_date)
    if date_format in ("gregorian", "both"):
        gregorian_date = f"{omer_date.day}/{omer_date.month}"
        date_parts.append(gregorian_date)

    # Combine date parts with sefirah
    if date_parts:
        sub_line = " | ".join(date_parts) + f" | {sefirah_text}"
    else:
        sub_line = sefirah_text

    fitted_sub_font = get_fitted_font(sub_line, sub_font, W - 100, rtl=True)
    draw_text_with_stroke(draw, (W//2, 145), sub_line, fitted_sub_font, fill, stroke, stroke_w, anchor="ma", rtl=True)

    # Omer content texts
    omer_blessing = "בָּרוּךְ אַתָּה יְיָ אֱלֹהֵינוּ מֶלֶךְ הָעוֹלָם, אֲשֶׁר קִדְּשָׁנוּ בְּמִצְוֹתָיו וְצִוָּנוּ עַל סְפִירַת הָעֹמֶר"
    omer_count = get_omer_count_text(omer_day)
    harachaman = "הָרַחֲמָן הוּא יַחֲזִיר לָנוּ עֲבוֹדַת בֵּית הַמִּקְדָּשׁ לִמְקוֹמָהּ, בִּמְהֵרָה בְיָמֵינוּ אָמֵן סֶלָה"

    # Handle bottom text area
    if blessing_text is None:
        blessing_text = ""
    if dedication_text is None:
        dedication_text = ""

    show_blessing = bool(blessing_text)
    show_dedication = bool(dedication_text)

    # Define fonts for content measurement
    blessing_font = load_font(32)
    count_font = load_font(70, bold=True)
    harachaman_font = load_font(28)

    # Calculate content width (with margins)
    content_width = W - 200
    text_area_width = content_width - 60  # Account for padding inside rectangle

    # Measure actual text heights
    # Blessing text height
    fitted_blessing_font = get_fitted_font(omer_blessing, blessing_font, text_area_width, rtl=True)
    blessing_bbox = fitted_blessing_font.getbbox(omer_blessing)
    blessing_height = blessing_bbox[3] - blessing_bbox[1]

    # Count text height (multi-line)
    count_lines = wrap_hebrew_text(omer_count, count_font, text_area_width)
    count_bbox = count_font.getbbox("אבגדהוזחט")  # Sample for line height
    count_line_height = count_bbox[3] - count_bbox[1] + 25  # 25 = line_spacing (increased for readability)
    count_height = len(count_lines) * count_line_height

    # Harachaman text height
    fitted_harachaman_font = get_fitted_font(harachaman, harachaman_font, text_area_width, rtl=True)
    harachaman_bbox = fitted_harachaman_font.getbbox(harachaman)
    harachaman_height = harachaman_bbox[3] - harachaman_bbox[1]

    # Calculate total content height with padding
    vertical_padding = 35  # Top and bottom padding inside rectangle
    spacing_after_blessing = 50
    spacing_after_count = 40
    content_height = (
        vertical_padding +
        blessing_height +
        spacing_after_blessing +
        count_height +
        spacing_after_count +
        harachaman_height +
        vertical_padding
    )

    # Position content area between 50-66% from top (centered around 58%)
    content_center_y = int(H * 0.58)
    content_top = content_center_y - content_height // 2

    # Ensure it doesn't overlap with title/subtitle (below ~200px) or bottom text
    min_top = 200
    if show_blessing and show_dedication:
        blessing_y = H - 125
        dedication_y = H - 50
        max_bottom = blessing_y - 30
    elif show_blessing and not show_dedication:
        blessing_y = H - 85
        max_bottom = blessing_y - 30
    elif not show_blessing and show_dedication:
        dedication_y = H - 50
        max_bottom = dedication_y - 30
    else:
        max_bottom = H - 40

    # Clamp content position
    content_top = max(min_top, content_top)
    if content_top + content_height > max_bottom:
        content_top = max_bottom - content_height

    # Create semi-transparent overlay for content area
    overlay = Image.new("RGBA", (content_width, content_height), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)

    corner_radius = 25
    overlay_draw.rounded_rectangle(
        [0, 0, content_width, content_height],
        radius=corner_radius,
        fill=(0, 0, 0, 70)
    )

    content_left = (W - content_width) // 2
    img.paste(overlay, (content_left, content_top), overlay)

    draw = ImageDraw.Draw(img)

    # Draw the Omer content
    y = content_top + vertical_padding

    # Blessing text
    draw_text_with_stroke(draw, (W//2, y), omer_blessing, fitted_blessing_font, fill, stroke, 3, anchor="ma", rtl=True)
    y += blessing_height + spacing_after_blessing

    # Count text (multi-line)
    count_text_height = draw_multiline_text_with_stroke(
        draw, (W//2, y), omer_count, count_font,
        fill, stroke, 4,
        max_width=text_area_width,
        line_spacing=25,  # Increased from 15 for better readability on multi-line count
        anchor="ma", rtl=True
    )
    y += count_text_height + spacing_after_count

    # Harachaman text
    draw_text_with_stroke(draw, (W//2, y), harachaman, fitted_harachaman_font, fill, stroke, 3, anchor="ma", rtl=True)

    # Draw bottom blessing and dedication text
    if show_blessing:
        draw_text_with_stroke(
            draw, (W//2, blessing_y),
            blessing_text, bless_font,
            fill, stroke, stroke_w,
            anchor="ma", rtl=True,
        )
    if show_dedication:
        draw_text_with_stroke(
            draw, (W//2, dedication_y),
            dedication_text, small_font,
            fill, stroke, 3,
            anchor="ma", rtl=True,
        )

    # Add watermark if enabled
    if show_watermark:
        img = overlay_watermark(
            img,
            watermark_path=WATERMARK_PATH,
            size=WATERMARK_SIZE,
            margin=WATERMARK_MARGIN,
            opacity=WATERMARK_OPACITY
        )

    return img


# ========= MAIN =========
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
    aspect_ratio: str = "1:1",  # Aspect ratio: "1:1", "4:5", or "auto"
    flexible_aspect: bool = False,  # DEPRECATED: Use aspect_ratio="auto" instead
    omer_mode: bool = False,  # Generate Sefirat HaOmer poster instead of Shabbat
    omer_date: Optional[date] = None,  # Date for Omer calculation (default: today)
    omer_day: Optional[int] = None,  # Direct Omer day (1-49), overrides date-based calculation
) -> bytes:
    """
    Generate a single Shabbat/Yom Tov poster for one background image.

    This is the main entry point for poster generation. It finds the next
    Shabbat or holiday sequence, calculates candle lighting and havdalah
    times for each city, and renders a beautiful poster image.

    When omer_mode=True, generates a Sefirat HaOmer poster instead, with:
    - Title: "ספירת העומר"
    - Subtitle: "Hebrew date | Gregorian date | Sefirah" (dates based on date_format)
    - Content area with blessing, larger multi-line count text, and Harachaman

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
        aspect_ratio: Output aspect ratio - "1:1" (1080x1080 square), "4:5" (1080x1350
                      portrait), or "auto" (preserve original image ratio within
                      constraints). Default: "1:1".
        flexible_aspect: DEPRECATED - Use aspect_ratio="auto" instead. If True and
                         aspect_ratio is "1:1", will be treated as aspect_ratio="auto".
        omer_mode: If True, generate a Sefirat HaOmer poster (default: False)
        omer_date: Date for Omer calculation. If None, uses today. If current hour
                   is between 00:00-06:00, counts for next day (after midnight logic).
        omer_day: Direct Omer day number (1-49). If provided, overrides omer_date
                  calculation. Useful for letting users select a specific day.

    Returns:
        PNG image bytes ready to be saved or transmitted
    """
    # Use defaults if not provided
    if start_date is None:
        start_date = date.today()
    if cities is None:
        cities = DEFAULT_CITIES  # Use neutral default cities

    # Handle backward compatibility: flexible_aspect=True maps to aspect_ratio="auto"
    effective_aspect_ratio = aspect_ratio
    if flexible_aspect and aspect_ratio == "1:1":
        effective_aspect_ratio = "auto"

    # Determine target size based on aspect ratio
    if effective_aspect_ratio == "auto":
        target_size = IMG_SIZE  # Max constraint for flexible mode
        use_flexible = True
    else:
        target_size = ASPECT_RATIO_SIZES.get(effective_aspect_ratio, IMG_SIZE)
        use_flexible = False

    # === OMER MODE ===
    if omer_mode:
        # If omer_day is directly specified, use it
        if omer_day is not None:
            if omer_day < 1 or omer_day > 49:
                raise ValueError(f"Omer day must be 1-49, got {omer_day}")
            effective_omer_day = omer_day
        else:
            # Calculate from date
            effective_omer_date = omer_date if omer_date else date.today()

            # Check if we're after midnight (00:00-06:00) - count for next day
            current_hour = datetime.now(pytz.timezone(TZID)).hour
            after_midnight = current_hour >= 0 and current_hour < 6

            # Get the Omer day
            effective_omer_day = get_omer_day(effective_omer_date, after_midnight=after_midnight)

            if effective_omer_day is None:
                raise ValueError(f"Date {effective_omer_date} is not within the Omer period (16 Nisan - Shavuot)")

        # Load and fit background image
        bg = fit_background(
            image_path, target_size,
            crop_position=crop_position,
            flexible_aspect=use_flexible,
        )

        # Compose the Omer poster
        # Use omer_date for display if available, otherwise today
        effective_omer_date = omer_date if omer_date else date.today()
        img = compose_omer_poster(
            bg, effective_omer_day,
            omer_date=effective_omer_date,
            blessing_text=blessing_text,
            dedication_text=dedication_text,
            date_format=date_format,
            show_watermark=show_watermark,
        )

        # Save to BytesIO buffer as PNG and return bytes
        buffer = BytesIO()
        img.save(buffer, format="PNG", optimize=True)
        return buffer.getvalue()

    # === SHABBAT/YOM TOV MODE ===
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

    # Check if input is a video file (MP4/WebM) - convert to animated GIF
    if is_video_file(image_path):
        # Extract frames from video
        frames, durations = extract_video_frames(image_path, max_frames=12)
        processed_frames = []

        for frame in frames:
            # Convert frame to RGB if needed
            if frame.mode != 'RGB':
                frame = frame.convert('RGB')

            # Fit the frame to target size
            frame = fix_image_orientation(frame)
            if use_flexible:
                bg = _fit_background_flexible(frame, target_size, crop_position)
            else:
                bg = _fit_background_fixed(frame, target_size, crop_position)

            # Compose the poster on this frame
            processed_frame = compose_poster(
                bg, week_info, rows,
                blessing_text=blessing_text,
                dedication_text=dedication_text,
                date_format=date_format,
                show_watermark=show_watermark,
            )
            processed_frames.append(processed_frame)

        # Assemble processed frames into animated GIF
        return assemble_gif(processed_frames, durations)

    # Check if input is an animated GIF
    if is_animated_gif(image_path):
        # Process animated GIF - apply poster overlay to each frame
        frames, durations = extract_gif_frames(image_path)
        processed_frames = []

        for frame in frames:
            # Convert frame to RGB if needed
            if frame.mode != 'RGB':
                frame = frame.convert('RGB')

            # Fit the frame to target size (process each frame like a static image)
            frame = fix_image_orientation(frame)
            if use_flexible:
                bg = _fit_background_flexible(frame, target_size, crop_position)
            else:
                bg = _fit_background_fixed(frame, target_size, crop_position)

            # Compose the poster on this frame
            processed_frame = compose_poster(
                bg, week_info, rows,
                blessing_text=blessing_text,
                dedication_text=dedication_text,
                date_format=date_format,
                show_watermark=show_watermark,
            )
            processed_frames.append(processed_frame)

        # Assemble processed frames into animated GIF
        return assemble_gif(processed_frames, durations)

    # Standard static image processing (PNG/JPG)
    bg = fit_background(
        image_path, target_size,
        crop_position=crop_position,
        flexible_aspect=use_flexible,
    )

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
