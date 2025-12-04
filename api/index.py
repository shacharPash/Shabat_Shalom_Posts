import os
import sys
from http.server import BaseHTTPRequestHandler

# Add parent directory to path for Vercel serverless environment
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from cities import get_cities_list


def generate_html() -> str:
    """Generate the HTML page with city checkboxes."""
    cities = get_cities_list()

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

