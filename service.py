import html
import os

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

from api.poster import build_poster_from_payload
from cities import get_cities_list
from poster_http import create_poster_response, register_public_routes


app = FastAPI()

# Load cities once at startup (cached internally)
GEOJSON_CITIES = get_cities_list()

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
async def create_poster(request: Request):
    return await create_poster_response(request, build_poster_from_payload)


register_public_routes(app)
