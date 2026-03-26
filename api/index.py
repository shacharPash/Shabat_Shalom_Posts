import html
import os
import sys
from http.server import BaseHTTPRequestHandler

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, Response

# Add parent directory to path for Vercel serverless environment
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from cities import get_cities_list, map_city_payload
from api.poster import build_poster_from_payload, CITY_BY_NAME

# FastAPI app for local development with `vercel dev`
app = FastAPI()


def generate_html() -> str:
    """Generate the HTML page with city checkboxes."""
    cities = get_cities_list()

    # Use html.escape to handle city names with quotes (e.g., עין הנצי"ב)
    city_checkboxes = "\n".join([
        f'        <div class="city-option" data-name="{html.escape(city["name"], quote=True)}" data-selected="false"><span class="city-check-icon">✓</span><span class="city-name">{html.escape(city["name"])}</span><div class="offset-input"><input type="number" class="candle-offset" value="{city["candle_offset"]}" min="0" max="60" title="דקות לפני השקיעה"><span class="offset-label">ד\'</span></div></div>'
        for city in cities
    ])

    # Read the HTML template from a file
    template_path = os.path.join(os.path.dirname(__file__), "template.html")
    with open(template_path, "r", encoding="utf-8") as f:
        html_template = f.read()

    return html_template.replace("CITY_CHECKBOXES_PLACEHOLDER", city_checkboxes)


class handler(BaseHTTPRequestHandler):
    """Vercel serverless function entrypoint for the root page."""

    def do_GET(self):
        try:
            html_content = generate_html()

            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html_content.encode("utf-8"))
        except Exception as e:
            error_msg = f"Internal Server Error: {e}".encode("utf-8")
            self.send_response(500)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(error_msg)


# FastAPI route for local development with `vercel dev`
@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main HTML page (for local dev)."""
    return generate_html()


@app.post("/poster")
async def create_poster(request: Request):
    """Create poster (for local dev)."""
    try:
        payload = await request.json()
        # Map city names to full city objects with coordinates (same as Vercel handler)
        map_city_payload(payload, CITY_BY_NAME)
        poster_bytes = build_poster_from_payload(payload)

        # Detect output format from magic bytes
        # GIF starts with "GIF87a" or "GIF89a", PNG starts with \x89PNG
        if poster_bytes[:6] in (b'GIF87a', b'GIF89a'):
            media_type = "image/gif"
        else:
            media_type = "image/png"

        return Response(content=poster_bytes, media_type=media_type)
    except Exception as e:
        return Response(content=str(e), status_code=500)
