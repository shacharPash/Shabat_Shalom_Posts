import html
import os
from typing import Any, Dict
from datetime import date, timedelta

from fastapi import FastAPI, Body
from fastapi.responses import Response, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from api.poster import build_poster_from_payload
from api.upcoming_events import get_upcoming_events
from cities import get_cities_list, build_city_lookup, map_city_payload
from make_shabbat_posts import find_next_sequence, get_parsha_from_hebcal
from translations import YOMTOV_TRANSLATIONS


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
    map_city_payload(payload, CITY_BY_NAME)

    poster_bytes = build_poster_from_payload(payload)
    return Response(content=poster_bytes, media_type="image/png")


@app.get("/upcoming-events")
async def upcoming_events_endpoint():
    """Get upcoming Shabbat/holiday events for one year ahead."""
    return get_upcoming_events()
