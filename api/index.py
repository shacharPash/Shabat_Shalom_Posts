import json
import os
from http.server import BaseHTTPRequestHandler
from typing import Any, Dict, List


def load_cities_from_geojson() -> List[Dict[str, Any]]:
    """Load and parse cities from the GeoJSON file."""
    try:
        geojson_path = os.path.join(os.path.dirname(__file__), "..", "cities_coordinates.geojson")
        with open(geojson_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        cities = []
        for feature in data.get("features", []):
            props = feature.get("properties", {})
            geometry = feature.get("geometry", {})
            coords = geometry.get("coordinates", [])

            name = props.get("MGLSDE_LOC", "").strip()
            population = props.get("MGLSDE_L_1", 0)
            if name and len(coords) >= 2:
                if name in ("ירושלים", "פתח תקווה"):
                    default_offset = 40
                elif name in ("חיפה", "מורשת"):
                    default_offset = 30
                else:
                    default_offset = 20
                cities.append({
                    "name": name,
                    "lat": coords[1],
                    "lon": coords[0],
                    "candle_offset": default_offset,
                    "population": population
                })

        cities.sort(key=lambda c: c["population"], reverse=True)
        return cities
    except Exception as e:
        print(f"Error loading GeoJSON: {e}")
        return []


def generate_html() -> str:
    """Generate the HTML page with city checkboxes."""
    cities = load_cities_from_geojson()
    
    city_checkboxes = "\n".join([
        f'        <div class="city-option" data-name="{city["name"]}"><input type="checkbox" name="cityOption" value="{city["name"]}"><span class="city-name">{city["name"]}</span><div class="offset-input"><input type="number" class="candle-offset" value="{city["candle_offset"]}" min="0" max="60" title="דקות לפני השקיעה"><span class="offset-label">ד\'</span></div></div>'
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

