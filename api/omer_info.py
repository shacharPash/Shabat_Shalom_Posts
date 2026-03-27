"""
Vercel serverless function for getting Omer day information.
"""

import json
import os
import sys
from datetime import date
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

# Add parent directory to path for Vercel serverless environment
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from omer_utils import get_omer_day, get_omer_count_text, get_sefirah_text


class handler(BaseHTTPRequestHandler):
    """Vercel serverless function entrypoint for Omer day information."""

    def do_GET(self):
        try:
            # Parse query parameters
            parsed_url = urlparse(self.path)
            query_params = parse_qs(parsed_url.query)

            # Get date parameter (optional, defaults to today)
            date_param = query_params.get("date", [None])[0]
            if date_param:
                target_date = date.fromisoformat(date_param)
            else:
                target_date = date.today()

            # Get Omer day
            omer_day = get_omer_day(target_date)

            if omer_day is None:
                # Not in Omer period
                response = {"isOmerPeriod": False}
            else:
                # In Omer period - get all the info
                response = {
                    "isOmerPeriod": True,
                    "dayNumber": omer_day,
                    "hebrewCount": get_omer_count_text(omer_day),
                    "sefirah": get_sefirah_text(omer_day),
                }

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "public, max-age=3600")  # Cache for 1 hour
            self.end_headers()
            self.wfile.write(json.dumps(response, ensure_ascii=False).encode("utf-8"))

        except ValueError as e:
            # Invalid date format
            error_response = {"error": f"Invalid date format: {e}"}
            self.send_response(400)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(error_response, ensure_ascii=False).encode("utf-8"))

        except Exception as e:
            error_response = {"error": str(e)}
            self.send_response(500)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(error_response, ensure_ascii=False).encode("utf-8"))

