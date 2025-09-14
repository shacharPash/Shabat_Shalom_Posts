import argparse
import os
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
import requests
from PIL import Image, ImageDraw, ImageFont
import arabic_reshaper
from bidi.algorithm import get_display

# ========= CONFIG =========
TZID = "Asia/Jerusalem"
CITIES = [
    {"name": "ירושלים", "lat": 31.7683, "lon": 35.2137, "candle_offset": 40},
    {"name": "תל אביב", "lat": 32.0853, "lon": 34.7818, "candle_offset": 20},
    {"name": "לוד", "lat": 31.951, "lon": 34.888, "candle_offset": 20},
    {"name": "אריאל", "lat": 32.106, "lon": 35.185, "candle_offset": 20},
    {"name": "מורשת", "lat": 32.86, "lon": 35.24, "candle_offset": 20},
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

# ========= DATA FROM HEBCAL =========
def hebcal_shabbat_for_week(lat: float, lon: float, start_dt: date, candle_offset: int) -> dict:
    start_str = (start_dt - timedelta(days=1)).isoformat()
    end_str   = (start_dt + timedelta(days=2)).isoformat()

    url = (
        "https://www.hebcal.com/shabbat"
        f"?cfg=json&latitude={lat}&longitude={lon}"
        f"&tzid={TZID}&start={start_str}&end={end_str}"
        f"&b={candle_offset}"   # candle-lighting offset in minutes before sunset
        "&m=42"                 # havdalah 42 minutes after sunset (can be changed)
    )

    r = requests.get(url, timeout=20)
    r.raise_for_status()
    data = r.json()

    parsha = None
    candle = None
    havdalah = None
    for item in data.get("items", []):
        cat = item.get("category")
        if cat == "parashat":
            parsha = item.get("title")
        elif cat == "candles" and candle is None:
            candle = item.get("date")
        elif cat == "havdalah" and havdalah is None:
            havdalah = item.get("date")

    if parsha:
        for eng, heb in PARASHA_TRANSLATION.items():
            if eng in parsha:
                parsha = f"פרשת {heb}"
                break

    return {"parsha": parsha, "candle": candle, "havdalah": havdalah}

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

    draw_text_with_stroke(draw, (W//2, 100), "שבת שלום", title_font, fill, stroke, stroke_w, anchor="ma", rtl=True)

    parsha_txt = week_info.get("parsha") or ""
    date_str = week_info.get("friday").strftime("%d.%m.%Y")
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

    draw_text_with_stroke(draw, (col_city_x, y), "עיר", row_font, fill, stroke, stroke_w, anchor="ra", rtl=True)
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

def main():
    parser = argparse.ArgumentParser(description="Generate Shabbat Shalom posts with candle times")
    parser.add_argument("--images-dir", default="images", help="Input images folder")
    parser.add_argument("--start-date", default=None, help="YYYY-MM-DD, default is today -> next Friday")
    args = parser.parse_args()

    if args.start_date:
        start_base = date.fromisoformat(args.start_date)
    else:
        start_base = date.today()
    first_friday = next_friday(start_base)

    exts = {".jpg", ".jpeg", ".png", ".webp"}
    images = [os.path.join(args.images_dir, f) for f in sorted(os.listdir(args.images_dir))]
    images = [p for p in images if os.path.splitext(p)[1].lower() in exts]
    if not images:
        raise SystemExit("No images found in input folder.")

    for i, img_path in enumerate(images):
        friday = first_friday + relativedelta(weeks=i)
        rows = []
        parsha_name = None
        for city in CITIES:
            info = hebcal_shabbat_for_week(city["lat"], city["lon"], friday, city["candle_offset"])
            if not parsha_name and info.get("parsha"):
                parsha_name = info["parsha"]
            candle_hhmm = iso_to_hhmm(info.get("candle"))
            hav_hhmm    = iso_to_hhmm(info.get("havdalah"))
            rows.append((city["name"], candle_hhmm, hav_hhmm))

        bg = fit_background(img_path, IMG_SIZE)
        week_info = {"parsha": parsha_name, "friday": friday}
        out_name = f"output/shabbat_{friday.isoformat()}_cities.png"
        compose_poster(bg, week_info, rows, out_name)

if __name__ == "__main__":
    main()
