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

# ========= CONFIG =========
TZID = "Asia/Jerusalem"
CITIES = [
    {"name": "ירושלים", "lat": 31.778117828230577, "lon": 35.23599222120022, "candle_offset": 40},
    {"name": "תל אביב", "lat": 32.08680752114438, "lon": 34.78974135330866, "candle_offset": 20},
    {"name": "לוד", "lat": 31.94588148808545, "lon": 34.88693992597191, "candle_offset": 20},
    {"name": "אריאל", "lat": 32.103147, "lon": 35.207642, "candle_offset": 20},
    {"name": "מורשת", "lat": 32.825819, "lon": 35.233452, "candle_offset": 20},
]

IMG_SIZE = (1080, 1080)  # WhatsApp square

# ========= FULL PARASHA TRANSLATION =========
PARASHA_TRANSLATION = {
    "Bereshit": "בראשית", "Noach": "נח", "Lech-Lecha": "לך לך", "Vayera": "וירא",
    "Chayei Sara": "חיי שרה", "Toldot": "תולדות", "Vayetzei": "ויצא",
    "Vayishlach": "וישלח", "Vayeshev": "וישב", "Miketz": "מקץ", "Vayigash": "ויגש",
    "Vayechi": "ויחי", "Shemot": "שמות", "Vaera": "וארא", "Bo": "בא",
    "Beshalach": "בשלח", "Yitro": "יתרו", "Mishpatim": "משפטים", "Terumah": "תרומה",
    "Tetzaveh": "תצוה", "Ki Tisa": "כי תשא", "Vayakhel": "ויקהל", "Pekudei": "פקודי",
    "Vayikra": "ויקרא", "Tzav": "צו", "Shemini": "שמיני", "Tazria": "תזריע",
    "Metzora": "מצורע", "Achrei Mot": "אחרי מות", "Kedoshim": "קדושים",
    "Emor": "אמור", "Behar": "בהר", "Bechukotai": "בחוקותי", "Bamidbar": "במדבר",
    "Nasso": "נשא", "Beha'alotcha": "בהעלותך", "Shelach": "שלח", "Korach": "קרח",
    "Chukat": "חוקת", "Balak": "בלק", "Pinchas": "פנחס", "Matot": "מטות",
    "Masei": "מסעי", "Devarim": "דברים", "Vaetchanan": "ואתחנן", "Ekev": "עקב",
    "Re'eh": "ראה", "Shoftim": "שופטים", "Ki Tetzei": "כי תצא", "Ki Tavo": "כי תבוא",
    "Nitzavim": "נצבים", "Vayelech": "וילך", "Ha'Azinu": "האזינו",
    "Vezot Haberakhah": "וזאת הברכה",
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

            # Get candle lighting time
            if zmanim_dict.get('hadlokas_haneiros'):
                candle_time = zmanim_dict['hadlokas_haneiros']

            # Get havdalah time (prefer stars over fixed minutes)
            if zmanim_dict.get('tzeis_hakochavim'):
                havdalah_time = zmanim_dict['tzeis_hakochavim']
            elif zmanim_dict.get('tzeis_minutes'):
                havdalah_time = zmanim_dict['tzeis_minutes']

    # Get parsha information from Hebcal (jewcal doesn't provide this)
    parsha = get_parsha_from_hebcal(target_date)

    return {
        "parsha": parsha,
        "event_name": event_name,
        "event_type": event_type,
        "candle": candle_time if candle_time else None,
        "havdalah": havdalah_time if havdalah_time else None,
        "action": jewcal.events.action if jewcal.has_events() else None
    }

def get_parsha_from_hebcal(start_dt: date) -> str:
    """Get parsha information from Hebcal API."""
    start_str = (start_dt - timedelta(days=1)).isoformat()
    end_str   = (start_dt + timedelta(days=2)).isoformat()

    url = (
        "https://www.hebcal.com/shabbat"
        f"?cfg=json&latitude=31.778117828230577&longitude=35.23599222120022"  # Jerusalem coordinates for parsha
        f"&tzid={TZID}&start={start_str}&end={end_str}"
    )

    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        data = r.json()

        for item in data.get("items", []):
            if item.get("category") == "parashat":
                parsha = item.get("title")
                if parsha:
                    for eng, heb in PARASHA_TRANSLATION.items():
                        if eng in parsha:
                            return f"פרשת {heb}"
                return parsha
    except Exception as e:
        print(f"Warning: Could not fetch parsha information: {e}")

    return None

def iso_to_hhmm(iso_str: str) -> str:
    if not iso_str:
        return "--:--"
    dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    return dt.strftime("%H:%M")

# ========= IMAGE HELPERS =========
def fit_background(image_path: str, size=(1080,1080)) -> Image.Image:
    base_w, base_h = size
    img = Image.open(image_path).convert("RGB")
    scale = max(base_w / img.width, base_h / img.height)
    new_w = int(img.width * scale)
    new_h = int(img.height * scale)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - base_w) // 2
    top  = (new_h - base_h) // 2
    img = img.crop((left, top, left + base_w, top + base_h))
    return img

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

    draw_text_with_stroke(draw, (W//2, 100), title, title_font, fill, stroke, stroke_w, anchor="ma", rtl=True)

    # Create subtitle with parsha and date
    parsha_txt = week_info.get("parsha") or ""
    event_date = week_info.get("event_date")
    date_str = event_date.strftime("%d.%m.%Y") if event_date else ""

    # Add event name for Yom Tov
    if event_type == "yomtov" and event_name:
        # Translate common Yom Tov names to Hebrew
        yomtov_translations = {
            "Rosh Hashana 1": "ראש השנה א'",
            "Rosh Hashana 2": "ראש השנה ב'",
            "Yom Kippur": "יום כפור",
            "Sukkos 1": "סוכות א'",
            "Sukkos 2": "סוכות ב'",
            "Shmini Atzeres": "שמיני עצרת",
            "Simchas Tora": "שמחת תורה",
            "Pesach 1": "פסח א'",
            "Pesach 2": "פסח ב'",
            "Pesach 7": "פסח ז'",
            "Pesach 8": "פסח ח'",
            "Shavuos 1": "שבועות א'",
            "Shavuos 2": "שבועות ב'",
            "Shavuos": "שבועות"
        }
        hebrew_event = yomtov_translations.get(event_name, event_name)
        if parsha_txt:
            sub_line = f"{hebrew_event} | {parsha_txt} | {date_str}"
        else:
            sub_line = f"{hebrew_event} | {date_str}"
    else:
        sub_line = f"{parsha_txt} | {date_str}" if parsha_txt else date_str

    draw_text_with_stroke(draw, (W//2, 200), sub_line, sub_font, fill, stroke, stroke_w, anchor="ma", rtl=True)

    table_top = 300
    table_height = (len(all_cities_rows)+1) * (row_font.size+20) + 60
    overlay = Image.new("RGBA", (W-100, table_height), (0,0,0,150))
    img.paste(overlay, (50, table_top), overlay)

    draw = ImageDraw.Draw(img)
    col_city_x   = W - 150
    col_candle_x = W - 550
    col_hav_x    = W - 850
    y = table_top + 60

    # Update column headers based on event type
    event_info = week_info.get("event_info", {})
    event_type = event_info.get("event_type", "shabbos")

    draw_text_with_stroke(draw, (col_city_x, y), "עיר", row_font, fill, stroke, stroke_w, anchor="ra", rtl=True)

    if event_type == "yomtov":
        draw_text_with_stroke(draw, (col_candle_x, y), "הדלקת נרות", row_font, fill, stroke, stroke_w, anchor="ra", rtl=True)
        draw_text_with_stroke(draw, (col_hav_x, y), "צאת החג", row_font, fill, stroke, stroke_w, anchor="ra", rtl=True)
    else:
        draw_text_with_stroke(draw, (col_candle_x, y), "כניסת שבת", row_font, fill, stroke, stroke_w, anchor="ra", rtl=True)
        draw_text_with_stroke(draw, (col_hav_x, y), "צאת שבת", row_font, fill, stroke, stroke_w, anchor="ra", rtl=True)
    y += row_font.size + 30

    for name, candle_hhmm, hav_hhmm in all_cities_rows:
        draw_text_with_stroke(draw, (col_city_x, y), name, row_font, fill, stroke, stroke_w, anchor="ra", rtl=True)
        draw_text_with_stroke(draw, (col_candle_x, y), candle_hhmm, row_font, fill, stroke, stroke_w, anchor="ra")
        draw_text_with_stroke(draw, (col_hav_x, y), hav_hhmm, row_font, fill, stroke, stroke_w, anchor="ra")
        y += row_font.size + 20

    draw_text_with_stroke(draw, (W//2, H - 150), "\"לחיי שמחות קטנות וגדולות\"", bless_font, fill, stroke, stroke_w, anchor="ma", rtl=True)
    draw_text_with_stroke(draw, (W//2, H - 80), 'זמני השבת לע"נ אורי בורנשטיין הי"ד', small_font, fill, stroke, 3, anchor="ma", rtl=True)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    img.save(out_path, format="PNG", optimize=True)
    print(f"Generated file: {out_path}")

# ========= MAIN =========
def next_friday(d: date) -> date:
    days_ahead = (4 - d.weekday()) % 7
    if days_ahead == 0 and datetime.now().hour >= 12:
        days_ahead = 7
    return d + timedelta(days=days_ahead)

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

    # Find the next event (Shabbat or Yom Tov)
    first_event_date, event_type, event_name = find_next_event_date(start_base)

    exts = {".jpg", ".jpeg", ".png", ".webp"}
    images = [os.path.join(args.images_dir, f) for f in sorted(os.listdir(args.images_dir))]
    images = [p for p in images if os.path.splitext(p)[1].lower() in exts]
    if not images:
        raise SystemExit("No images found in input folder.")

    for i, img_path in enumerate(images):
        # For subsequent images, find the next event after the current one
        if i == 0:
            event_date = first_event_date
        else:
            event_date, event_type, event_name = find_next_event_date(first_event_date + timedelta(days=7*i))

        rows = []
        parsha_name = None
        event_info = None

        for city in CITIES:
            info = jewcal_times_for_date(city["lat"], city["lon"], event_date, city["candle_offset"])
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
            "event_date": event_date,
            "event_info": event_info
        }

        # Create filename based on event type
        event_type_str = event_info.get("event_type", "shabbos")
        out_name = f"output/{event_type_str}_{event_date.isoformat()}_cities.png"
        compose_poster(bg, week_info, rows, out_name)

if __name__ == "__main__":
    main()
