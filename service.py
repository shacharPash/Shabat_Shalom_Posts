import html
import os
from typing import Any, Dict
from datetime import date, timedelta

from fastapi import FastAPI, Body
from fastapi.responses import Response, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from api.poster import build_poster_from_payload
from cities import get_cities_list, build_city_lookup
from make_shabbat_posts import find_next_sequence, get_parsha_from_hebcal


app = FastAPI()

# Mount static files directory
static_dir = os.path.join(os.path.dirname(__file__), "public", "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


# Favicon route at root level (browsers look for /favicon.ico)
@app.get("/favicon.ico")
async def favicon():
    favicon_path = os.path.join(static_dir, "favicon.ico")
    if os.path.isfile(favicon_path):
        return FileResponse(favicon_path, media_type="image/x-icon")
    return Response(status_code=404)


# Load cities once at startup (cached internally)
GEOJSON_CITIES = get_cities_list()
CITY_BY_NAME = build_city_lookup(GEOJSON_CITIES)

@app.get("/", response_class=HTMLResponse)
async def index():
    # Generate city checkboxes dynamically from GeoJSON data with offset input
    # Use html.escape to handle city names with quotes (e.g., עין הנצי"ב)
    city_checkboxes = "\n".join([
        f'        <div class="city-option" data-name="{html.escape(city["name"], quote=True)}" data-selected="false"><span class="city-check-icon">✓</span><span class="city-name">{html.escape(city["name"])}</span><div class="offset-input"><input type="number" class="candle-offset" value="{city["candle_offset"]}" min="0" max="60" title="דקות לפני השקיעה"><span class="offset-label">ד\'</span></div></div>'
        for city in GEOJSON_CITIES
    ])

    # Read HTML template from shared file (single source of truth)
    template_path = os.path.join(os.path.dirname(__file__), "api", "template.html")
    with open(template_path, "r", encoding="utf-8") as f:
        html_template = f.read()

    return html_template.replace("CITY_CHECKBOXES_PLACEHOLDER", city_checkboxes)




@app.post("/poster")
async def create_poster(payload: Dict[str, Any] = Body(default={})):
    """
    FastAPI endpoint that:
    - Receives JSON payload
    - Uses build_poster_from_payload to generate a PNG
    - Returns image/png as response

    If payload contains 'cities' as a list of city objects (with name and candle_offset),
    maps them to full city objects with coordinates from GeoJSON.
    """
    if payload is None:
        payload = {}

    # Map city names to full city objects with coordinates
    if "cities" in payload and isinstance(payload["cities"], list):
        city_items = payload["cities"]
        mapped_cities = []
        for item in city_items:
            # Handle both old format (string) and new format (object with name and candle_offset)
            if isinstance(item, str):
                name = item
                candle_offset = 20
            elif isinstance(item, dict):
                name = item.get("name", "")
                candle_offset = item.get("candle_offset", 20)
            else:
                continue

            if name in CITY_BY_NAME:
                city = CITY_BY_NAME[name].copy()
                city["candle_offset"] = candle_offset  # Override with user's offset
                mapped_cities.append(city)

        # Only use mapped cities if we found at least one
        if mapped_cities:
            payload["cities"] = mapped_cities
        else:
            # No valid predefined cities found
            # If user has custom cities, set empty list (don't fall back to defaults)
            # Otherwise, remove to trigger default cities
            if "customCities" in payload and payload["customCities"]:
                payload["cities"] = []
            else:
                del payload["cities"]

    poster_bytes = build_poster_from_payload(payload)
    return Response(content=poster_bytes, media_type="image/png")


@app.get("/upcoming-events")
async def get_upcoming_events():
    """Get upcoming Shabbat/holiday events for one year ahead."""
    events = []
    current_date = date.today()
    # Calculate end date as one year from today
    one_year_ahead = date(current_date.year + 1, current_date.month, current_date.day)

    i = 0
    while current_date < one_year_ahead:
        seq_start, seq_end, event_type, event_name = find_next_sequence(current_date)

        # Get parsha for Shabbat
        parsha = None
        if event_type == "shabbos" or seq_end.weekday() == 5:  # Saturday
            parsha = get_parsha_from_hebcal(seq_end)

        # Format event name in Hebrew
        if event_type == "shabbos":
            display_name = parsha if parsha else "שבת"
        else:
            # Translate common Yom Tov names to Hebrew
            yomtov_translations = {
                "Rosh Hashana": "ראש השנה",
                "Rosh Hashanah": "ראש השנה",
                "Yom Kippur": "יום כיפור",
                "Sukkos": "סוכות",
                "Sukkot": "סוכות",
                "Shmini Atzeres": "שמיני עצרת",
                "Shemini Atzeret": "שמיני עצרת",
                "Simchas Torah": "שמחת תורה",
                "Simchat Torah": "שמחת תורה",
                "Pesach": "פסח",
                "Passover": "פסח",
                "Shavuos": "שבועות",
                "Shavuot": "שבועות",
                "Chanukah": "חנוכה",
                "Hanukkah": "חנוכה",
                "Purim": "פורים",
                "Tu BiShvat": "ט״ו בשבט",
                "Tu B'Shvat": "ט״ו בשבט",
                "Lag BaOmer": "ל״ג בעומר",
                "Lag B'Omer": "ל״ג בעומר",
                "Tisha B'Av": "תשעה באב",
                "Yom HaShoah": "יום השואה",
                "Yom HaZikaron": "יום הזיכרון",
                "Yom HaAtzmaut": "יום העצמאות",
                "Yom Yerushalayim": "יום ירושלים",
                "Chol HaMoed": "חול המועד",
                "Shmini Atzeret": "שמיני עצרת",
                "Simchat Tora": "שמחת תורה",
                "Shmini Atzeret / Simchat Tora": "שמיני עצרת / שמחת תורה",
            }
            # Try exact match first, then try partial match for variations like "Pesach I"
            display_name = yomtov_translations.get(event_name)
            if not display_name:
                # Try matching prefix (for "Pesach I", "Sukkot II", etc.)
                for eng, heb in yomtov_translations.items():
                    if event_name.startswith(eng):
                        display_name = heb
                        break
                else:
                    display_name = event_name

            # For Chol HaMoed on Shabbat (Saturday), show "שבת חול המועד"
            is_shabbat = seq_end.weekday() == 5  # Saturday
            if "Chol HaMoed" in event_name and is_shabbat:
                display_name = "שבת חול המועד"
            # For holidays on Shabbat, only show the holiday name (no parsha)

        # Format date in Hebrew style
        date_str = f"{seq_start.day}/{seq_start.month}"
        if seq_start != seq_end:
            date_str += f" - {seq_end.day}/{seq_end.month}"

        events.append({
            "startDate": seq_start.isoformat(),
            "endDate": seq_end.isoformat(),
            "eventType": event_type,
            "eventName": event_name,
            "displayName": display_name,
            "parsha": parsha,  # Include parsha separately for search
            "dateStr": date_str,
            "isNext": i == 0,
        })

        # Move to day after this sequence ends
        current_date = seq_end + timedelta(days=1)
        i += 1

    return events
