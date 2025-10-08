import argparse
import os
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
import requests
from PIL import Image, ImageDraw, ImageFont
import arabic_reshaper
from bidi.algorithm import get_display
from jewcal import JewCal
from jewcal.models.zmanim import Location
import pytz

# ========= CONFIG =========
TZID = "Asia/Jerusalem"
CITIES = [
    {"name": "ירושלים", "lat": 31.778117828230577, "lon": 35.23599222120022, "candle_offset": 40},
    {"name": "תל אביב", "lat": 32.08680752114438, "lon": 34.78974135330866, "candle_offset": 20},
    {"name": "לוד", "lat": 31.94588148808545, "lon": 34.88693992597191, "candle_offset": 20},
    {"name": "מורשת", "lat": 32.825819, "lon": 35.233452, "candle_offset": 20},
]

IMG_SIZE = (1080, 1080)  # Wider rectangle (5:4 ratio)

# ========= FULL PARASHA TRANSLATION =========
PARASHA_TRANSLATION = {
    # ספר בראשית
    "Bereshit": "בראשית", "Noach": "נח", "Lech-Lecha": "לך לך", "Vayera": "וירא",
    "Chayei Sara": "חיי שרה", "Toldot": "תולדות", "Vayetzei": "ויצא",
    "Vayishlach": "וישלח", "Vayeshev": "וישב", "Miketz": "מקץ", "Vayigash": "ויגש",
    "Vayechi": "ויחי",

    # ספר שמות
    "Shemot": "שמות", "Vaera": "וארא", "Bo": "בא",
    "Beshalach": "בשלח", "Yitro": "יתרו", "Mishpatim": "משפטים", "Terumah": "תרומה",
    "Tetzaveh": "תצוה", "Ki Tisa": "כי תשא", "Vayakhel": "ויקהל", "Pekudei": "פקודי",

    # ספר ויקרא
    "Vayikra": "ויקרא", "Tzav": "צו", "Shemini": "שמיני", "Tazria": "תזריע",
    "Metzora": "מצורע", "Achrei Mot": "אחרי מות", "Kedoshim": "קדושים",
    "Emor": "אמור", "Behar": "בהר", "Bechukotai": "בחוקותי",

    # ספר במדבר
    "Bamidbar": "במדבר", "Nasso": "נשא", "Beha'alotcha": "בהעלותך", "Shelach": "שלח",
    "Korach": "קרח", "Chukat": "חוקת", "Balak": "בלק", "Pinchas": "פנחס",
    "Matot": "מטות", "Masei": "מסעי",

    # ספר דברים
    "Devarim": "דברים", "Vaetchanan": "ואתחנן", "Ekev": "עקב",
    "Re'eh": "ראה", "Shoftim": "שופטים", "Ki Tetzei": "כי תצא", "Ki Tavo": "כי תבוא",
    "Nitzavim": "נצבים", "Vayelech": "וילך", "Ha'Azinu": "האזינו",
    "Vezot Haberakhah": "וזאת הברכה",

    # וריאציות נוספות שעלולות להופיע ב-API
    "Lech Lecha": "לך לך", "Chayei Sarah": "חיי שרה", "Vayeitzei": "ויצא",
    "Ki Sisa": "כי תשא", "Acharei Mot": "אחרי מות", "Bechukosai": "בחוקותי",
    "Beha'aloscha": "בהעלותך", "Shlach": "שלח", "Chukas": "חוקת",
    "Matos": "מטות", "Mas'ei": "מסעי", "Va'eschanan": "ואתחנן",
    "Re'e": "ראה", "Ki Seitzei": "כי תצא", "Ki Savo": "כי תבוא",
    "Vayeilech": "וילך", "Haazinu": "האזינו", "Ha'azinu": "האזינו", "Ha'Azinu": "האזינו", "Ha'azinu": "האזינו",
    "V'Zot HaBerachah": "וזאת הברכה", "Vzot Haberachah": "וזאת הברכה",
}

# ========= TEXT HELPERS =========
def fix_hebrew(text: str) -> str:
    if not text:
        return text
    return get_display(arabic_reshaper.reshape(text))

def load_font(size: int, bold=False) -> ImageFont.FreeTypeFont:
    candidates = [
        "Alef-Bold.ttf" if bold else "Alef-Regular.ttf",
        "Alef-Regular.ttf",
        "DejaVuSans.ttf",
    ]
    for path in candidates:
        if os.path.isfile(path):
            try:
                return ImageFont.truetype(path, size=size)
            except Exception:
                continue
    return ImageFont.load_default()



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
    """Check if target_date is the end of a holiday sequence (should have havdalah)."""
    from jewcal import JewCal

    # Check if the next day also has a holiday/shabbat
    next_day = target_date + timedelta(days=1)
    next_jewcal = JewCal(gregorian_date=next_day, diaspora=False)

    # If next day has events that require candle lighting, current day is not the end
    if (next_jewcal.has_events() and
        next_jewcal.events.action in ["Candles", "Havdalah"]):
        return False

    return True

def jewcal_times_for_sequence(lat: float, lon: float, start_date: date, end_date: date, candle_offset: int) -> dict:
    """Calculate times for a complete event sequence (Shabbat or holiday sequence)."""

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

def get_parsha_from_hebcal(target_date: date) -> str:
    """Get parsha information from Hebcal API for the week containing target_date."""

    # Special cases for Torah reading during holidays
    from jewcal import JewCal
    jewcal = JewCal(gregorian_date=target_date, diaspora=False)
    if jewcal.has_events() and jewcal.events.yomtov:
        event_name = jewcal.events.yomtov
        # Simchat Torah, Hoshana Rabba, and Chol HaMoed Sukkot read "Vezot Haberakhah"
        if ("Simchat Tora" in event_name or
            "Shmini Atzeret / Simchat Tora" in event_name or
            "Hoshana Rabba" in event_name or
            "Chol HaMoed" in event_name):
            return "פרשת וזאת הברכה"

    # Find the Saturday of the week containing target_date
    days_until_saturday = (5 - target_date.weekday()) % 7  # Saturday is weekday 5
    if days_until_saturday == 0 and target_date.weekday() == 5:  # If target_date is Saturday
        saturday = target_date
    else:
        saturday = target_date + timedelta(days=days_until_saturday)

    # Use the general Hebcal API to get the year's events and find the right parsha
    year = saturday.year
    url = (
        f"https://www.hebcal.com/hebcal?v=1&cfg=json&maj=on&min=on&mod=on&nx=on"
        f"&year={year}&month=x&ss=on&mf=on&c=on&geo=pos"
        f"&latitude=31.778117828230577&longitude=35.23599222120022"
        f"&tzid={TZID}&s=on"
    )

    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        data = r.json()

        # Find the parsha for our specific Saturday
        target_date_str = saturday.isoformat()

        for item in data.get("items", []):
            if item.get("category") == "parashat":
                item_date = item.get("date", "")
                # Check if this is the parsha for our Saturday
                if item_date == target_date_str:
                    parsha = item.get("title")
                    if parsha:
                        # Clean up the parsha name and translate to Hebrew
                        parsha_clean = parsha.replace("Parashat ", "").strip()
                        # Normalize different types of apostrophes
                        parsha_clean = parsha_clean.replace("\u2019", "'").replace("\u2018", "'")


                        # Try exact match first
                        for eng, heb in PARASHA_TRANSLATION.items():
                            if eng.lower() == parsha_clean.lower():
                                return f"פרשת {heb}"

                        # Try partial match (for cases like "Ha'azinu" vs "Ha'Azinu")
                        for eng, heb in PARASHA_TRANSLATION.items():
                            if eng.lower().replace("'", "").replace("-", "") == parsha_clean.lower().replace("'", "").replace("-", ""):
                                # print(f"DEBUG: Found partial match: {eng} -> {heb}")
                                return f"פרשת {heb}"


                        return f"פרשת {parsha_clean}"

        # If exact match not found, find the closest Saturday before our target
        closest_parsha = None
        closest_date = None

        for item in data.get("items", []):
            if item.get("category") == "parashat":
                item_date_str = item.get("date", "")
                if item_date_str:
                    try:
                        item_date = date.fromisoformat(item_date_str)
                        # Find the parsha for the Saturday closest to but not after our target
                        if item_date <= saturday:
                            if closest_date is None or item_date > closest_date:
                                closest_date = item_date
                                closest_parsha = item.get("title")
                    except:
                        continue

        if closest_parsha:
            parsha_clean = closest_parsha.replace("Parashat ", "").strip()
            # Normalize different types of apostrophes
            parsha_clean = parsha_clean.replace("'", "'").replace("'", "'")
            # Try exact match first
            for eng, heb in PARASHA_TRANSLATION.items():
                if eng.lower() == parsha_clean.lower():
                    return f"פרשת {heb}"

            # Try partial match
            for eng, heb in PARASHA_TRANSLATION.items():
                if eng.lower().replace("'", "").replace("-", "") == parsha_clean.lower().replace("'", "").replace("-", ""):
                    return f"פרשת {heb}"

            return f"פרשת {parsha_clean}"

    except Exception as e:
        print(f"Warning: Could not fetch parsha information for {target_date}: {e}")

    return None

def iso_to_hhmm(iso_str: str) -> str:
    if not iso_str:
        return "--:--"

    # Parse the datetime string
    dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))

    # Convert to Israel timezone
    israel_tz = pytz.timezone('Asia/Jerusalem')
    if dt.tzinfo is None:
        # If no timezone info, assume UTC
        dt = pytz.utc.localize(dt)

    # Convert to Israel time
    israel_time = dt.astimezone(israel_tz)
    return israel_time.strftime("%H:%M")

# ========= IMAGE HELPERS =========
def fix_image_orientation(img):
    """Fix image orientation based on EXIF data."""
    try:
        exif = img._getexif()
        if exif is not None:
            orientation = exif.get(274)  # 274 is the EXIF orientation tag
            if orientation == 3:
                img = img.rotate(180, expand=True)
            elif orientation == 6:
                img = img.rotate(270, expand=True)
            elif orientation == 8:
                img = img.rotate(90, expand=True)
    except (AttributeError, KeyError, TypeError):
        pass
    return img

def fit_background(image_path: str, size=(1080,1080)) -> Image.Image:
    base_w, base_h = size
    img = Image.open(image_path).convert("RGB")

    # Fix orientation based on EXIF data
    img = fix_image_orientation(img)

    scale = max(base_w / img.width, base_h / img.height)
    new_w = int(img.width * scale)
    new_h = int(img.height * scale)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - base_w) // 2
    top  = (new_h - base_h) // 2
    img = img.crop((left, top, left + base_w, top + base_h))
    return img

def get_text_width(text, font, rtl=False):
    """Get the width of text with the given font."""
    if rtl:
        text = fix_hebrew(text)
    bbox = font.getbbox(text)
    return bbox[2] - bbox[0]

def get_fitted_font(text, original_font, max_width, rtl=False, min_size=20):
    """Get a font that fits the text within max_width."""
    current_size = original_font.size

    # Check if original font fits
    if get_text_width(text, original_font, rtl) <= max_width:
        return original_font

    # Find the largest font size that fits
    while current_size > min_size:
        current_size -= 2
        test_font = load_font(current_size, bold=original_font.path.endswith('Bold.ttf'))
        if get_text_width(text, test_font, rtl) <= max_width:
            return test_font

    # Return minimum size font if nothing fits
    return load_font(min_size, bold=original_font.path.endswith('Bold.ttf'))

def draw_text_with_stroke(draw, xy, text, font, fill, stroke_fill, stroke_width, anchor=None, rtl=False):
    if rtl:
        text = fix_hebrew(text)
    draw.text(
        xy, text, font=font, fill=fill,
        stroke_width=stroke_width, stroke_fill=stroke_fill,
        anchor=anchor
    )

# ========= COMPOSER =========
def compose_poster(bg_img: Image.Image, week_info: dict, all_cities_rows: list, out_path: str):
    img = bg_img.copy()
    W, H = img.size
    draw = ImageDraw.Draw(img)

    title_font = load_font(100, bold=True)
    sub_font   = load_font(54)
    row_font   = load_font(50)
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

    # התאמת גודל פונט לכותרת הראשית
    fitted_title_font = get_fitted_font(title, title_font, W - 100, rtl=True)
    draw_text_with_stroke(draw, (W//2, 40), title, fitted_title_font, fill, stroke, stroke_w, anchor="ma", rtl=True)

    # Create subtitle with parsha and date range
    parsha_txt = week_info.get("parsha") or ""
    seq_start = week_info.get("seq_start")
    seq_end = week_info.get("seq_end")

    if seq_start and seq_end:
        if seq_start == seq_end:
            date_str = seq_start.strftime("%d.%m.%Y")
        else:
            # Format: 22-24.09.2025 (day range with single month.year)
            if seq_start.month == seq_end.month and seq_start.year == seq_end.year:
                date_str = f"{seq_start.day}-{seq_end.day}.{seq_end.month:02d}.{seq_end.year}"
            else:
                # Different months: 30.09-02.10.2025
                date_str = f"{seq_start.strftime('%d.%m')}-{seq_end.strftime('%d.%m.%Y')}"
    else:
        date_str = ""

    # Add event name for Yom Tov
    if event_type == "yomtov" and event_name:
        # Translate common Yom Tov names to Hebrew
        yomtov_translations = {
            # Rosh Hashana
            "Erev Rosh Hashana": "ערב ראש השנה",
            "Rosh Hashana 1": "ראש השנה א'",
            "Rosh Hashana 2": "ראש השנה ב'",
            "Rosh Hashana": "ראש השנה",

            # Yom Kippur
            "Erev Yom Kippur": "ערב יום כיפור",
            "Yom Kippur": "יום כיפור",

            # Sukkot
            "Erev Sukkos": "ערב סוכות",
            "Erev Sukkot": "ערב סוכות",
            "Sukkos 1": "סוכות א'",
            "Sukkos 2": "סוכות ב'",
            "Sukkot 1": "סוכות א'",
            "Sukkot": "סוכות",
            "Sukkos": "סוכות",
            "Hoshana Rabba": "הושענא רבה",
            "Shmini Atzeres": "שמיני עצרת",
            "Shmini Atzeret": "שמיני עצרת",
            "Simchas Tora": "שמחת תורה",
            "Simchat Tora": "שמחת תורה",
            "Shmini Atzeret / Simchat Tora": "שמיני עצרת / שמחת תורה",

            # Pesach
            "Erev Pesach": "ערב פסח",
            "Pesach 1": "פסח א'",
            "Pesach 2": "פסח ב'",
            "Pesach 7": "שביעי של פסח",
            "Pesach 8": "פסח ח'",
            "Pesach": "פסח",

            # Shavuos
            "Erev Shavuos": "ערב שבועות",
            "Erev Shavut": "ערב שבועות",
            "Shavuos 1": "שבועות א'",
            "Shavuos 2": "שבועות ב'",
            "Shavuos": "שבועות",
            "Shavut": "שבועות",

            # Chol HaMoed
            "Chol HaMoed": "חול המועד",
            "Chol HaMoed 1": "חול המועד",
            "Chol HaMoed 2": "חול המועד",
            "Chol HaMoed 3": "חול המועד",
            "Chol HaMoed 4": "חול המועד",
            "Chol HaMoed 5": "חול המועד",
            "Chol HaMoed 1 (Sukkot 2)": "חול המועד סוכות",
            "Chol HaMoed 2 (Sukkot 3)": "חול המועד סוכות",
            "Chol HaMoed 3 (Sukkot 4)": "חול המועד סוכות",
            "Chol HaMoed 4 (Sukkot 5)": "חול המועד סוכות",
            "Chol HaMoed 5 (Sukkot 6)": "חול המועד סוכות",
            "Hoshana Rabba (Sukkot 7)": "הושענא רבה",
        }
        hebrew_event = yomtov_translations.get(event_name, event_name)
        if parsha_txt:
            sub_line = f"{hebrew_event} | {parsha_txt} | {date_str}"
        else:
            sub_line = f"{hebrew_event} | {date_str}"
    else:
        sub_line = f"{parsha_txt} | {date_str}" if parsha_txt else date_str

    # התאמת גודל פונט לכותרת המשנה
    fitted_sub_font = get_fitted_font(sub_line, sub_font, W - 100, rtl=True)
    draw_text_with_stroke(draw, (W//2, 140), sub_line, fitted_sub_font, fill, stroke, stroke_w, anchor="ma", rtl=True)

    # הזזת הטבלה למטה ושינוי גודל
    table_top = H - 450  # מתחיל 400 פיקסלים מהתחתית
    table_height = (len(all_cities_rows)+1) * (row_font.size+10) + 40
    table_width = W - 200  # רוחב קטן יותר

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

    # כותרות עמודות - ממורכזות
    draw_text_with_stroke(draw, (col_city_x, y), "עיר", row_font, fill, stroke, stroke_w, anchor="ma", rtl=True)

    if event_type == "yomtov":
        draw_text_with_stroke(draw, (col_candle_x, y), "הדלקת נרות", row_font, fill, stroke, stroke_w, anchor="ma", rtl=True)
        draw_text_with_stroke(draw, (col_hav_x, y), "צאת החג", row_font, fill, stroke, stroke_w, anchor="ma", rtl=True)
    else:
        draw_text_with_stroke(draw, (col_candle_x, y), "כניסת שבת", row_font, fill, stroke, stroke_w, anchor="ma", rtl=True)
        draw_text_with_stroke(draw, (col_hav_x, y), "צאת שבת", row_font, fill, stroke, stroke_w, anchor="ma", rtl=True)
    y += row_font.size + 10

    for name, candle_hhmm, hav_hhmm in all_cities_rows:
        # נתונים ממורכזים בכל עמודה
        draw_text_with_stroke(draw, (col_city_x, y), name, row_font, fill, stroke, stroke_w, anchor="ma", rtl=True)
        draw_text_with_stroke(draw, (col_candle_x, y), candle_hhmm, row_font, fill, stroke, stroke_w, anchor="ma")
        draw_text_with_stroke(draw, (col_hav_x, y), hav_hhmm, row_font, fill, stroke, stroke_w, anchor="ma")
        y += row_font.size + 8

    # הזזת הטקסטים מתחת לטבלה - במיקום קבוע למטה
    blessing_y = H - 110
    dedication_y = H - 50

    draw_text_with_stroke(draw, (W//2, blessing_y), "\"לחיי שמחות קטנות וגדולות\"", bless_font, fill, stroke, stroke_w, anchor="ma", rtl=True)
    draw_text_with_stroke(draw, (W//2, dedication_y), 'זמני השבת לע"נ אורי בורנשטיין הי"ד', small_font, fill, stroke, 3, anchor="ma", rtl=True)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    img.save(out_path, format="PNG", optimize=True)
    print(f"Generated file: {out_path}")

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

    for i, img_path in enumerate(images):
        # Find the next sequence
        seq_start, seq_end, event_type, event_name = find_next_sequence(current_search_date)

        # Skip if we've already processed this sequence
        if any(seq_start <= existing_end and seq_end >= existing_start
               for existing_start, existing_end in processed_sequences):
            # Move search date past this sequence
            current_search_date = seq_end + timedelta(days=1)
            seq_start, seq_end, event_type, event_name = find_next_sequence(current_search_date)

        processed_sequences.append((seq_start, seq_end))

        rows = []
        parsha_name = None
        event_info = None

        for city in CITIES:
            info = jewcal_times_for_sequence(city["lat"], city["lon"], seq_start, seq_end, city["candle_offset"])
            if not parsha_name and info.get("parsha"):
                parsha_name = info["parsha"]
            if not event_info:
                event_info = {
                    "event_name": info.get("event_name"),
                    "event_type": info.get("event_type"),
                    "action": info.get("action")
                }
            candle_hhmm = iso_to_hhmm(info.get("candle"))
            hav_hhmm    = iso_to_hhmm(info.get("havdalah"))
            rows.append((city["name"], candle_hhmm, hav_hhmm))

        bg = fit_background(img_path, IMG_SIZE)
        week_info = {
            "parsha": parsha_name,
            "seq_start": seq_start,
            "seq_end": seq_end,
            "event_info": event_info
        }

        # Create filename based on event type and sequence
        event_type_str = event_info.get("event_type", "shabbos")
        if seq_start == seq_end:
            out_name = f"output/{event_type_str}_{seq_start.isoformat()}_cities.png"
        else:
            out_name = f"output/{event_type_str}_{seq_start.isoformat()}_to_{seq_end.isoformat()}_cities.png"
        compose_poster(bg, week_info, rows, out_name)

        # Move to next sequence
        current_search_date = seq_end + timedelta(days=1)

if __name__ == "__main__":
    main()
