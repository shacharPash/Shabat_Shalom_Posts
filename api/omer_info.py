"""
Vercel serverless function for getting Omer day information.

Supports enhanced UX with sunset times, default day selection, and test mode.
"""

import json
import os
import sys
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

import pytz

# Add parent directory to path for Vercel serverless environment
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from omer_utils import (
    get_omer_day,
    get_omer_count_text,
    get_sefirah_text,
    get_omer_info_for_time,
)

# Israel timezone for current time
ISRAEL_TZ = pytz.timezone("Asia/Jerusalem")


class handler(BaseHTTPRequestHandler):
    """Vercel serverless function entrypoint for Omer day information."""

    def do_GET(self):
        try:
            # Parse query parameters
            parsed_url = urlparse(self.path)
            query_params = parse_qs(parsed_url.query)

            # Check for testTime parameter (for development testing)
            # Format: ?testTime=2026-04-15T22:30
            test_time_param = query_params.get("testTime", [None])[0]

            if test_time_param:
                # Parse test time
                try:
                    test_datetime = datetime.fromisoformat(test_time_param)
                    target_date = test_datetime.date()
                    current_hour = test_datetime.hour
                    current_minute = test_datetime.minute
                except ValueError:
                    raise ValueError(f"Invalid testTime format: {test_time_param}. Use ISO format like 2026-04-15T22:30")
            else:
                # Get date parameter (optional, defaults to today)
                date_param = query_params.get("date", [None])[0]
                if date_param:
                    target_date = date.fromisoformat(date_param)
                    # When a specific date is provided without testTime,
                    # use evening time (20:00) as the default context
                    current_hour = 20
                    current_minute = 0
                else:
                    # Use actual current time in Israel timezone
                    now = datetime.now(ISRAEL_TZ)
                    target_date = now.date()
                    current_hour = now.hour
                    current_minute = now.minute

            # Get comprehensive Omer info including sunset times
            omer_info = get_omer_info_for_time(target_date, current_hour, current_minute)

            # For backward compatibility, also include dayNumber if in Omer period
            if omer_info.get("isOmerPeriod"):
                default_day = omer_info.get("defaultDay")
                if default_day:
                    omer_info["dayNumber"] = default_day

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            # Shorter cache for dynamic time-based data
            self.send_header("Cache-Control", "public, max-age=300")  # Cache for 5 minutes
            self.end_headers()
            self.wfile.write(json.dumps(omer_info, ensure_ascii=False).encode("utf-8"))

        except ValueError as e:
            # Invalid date format
            print(f"Omer info validation error: {e}")  # Log full details
            error_response = {"error": "פורמט תאריך לא תקין"}
            self.send_response(400)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(error_response, ensure_ascii=False).encode("utf-8"))

        except Exception as e:
            print(f"Omer info error: {e}")  # Log full details
            error_response = {"error": "שגיאה בקבלת מידע העומר"}
            self.send_response(500)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(error_response, ensure_ascii=False).encode("utf-8"))

