"""
Vercel Cron endpoint for Shabbat/Holiday Eve reminders.

Runs on Friday mornings (8:00 Israel time = 5:00 UTC summer / 6:00 UTC winter).
Sends Shabbat/Holiday poster to all users with shabbat_reminder_enabled=True.

Query Parameters:
    test_user_id: (optional) Send reminder to specific user for testing.
                  Bypasses the Friday/Erev check. Example: ?test_user_id=123456789
"""

import base64
import json
import os
import sys
from datetime import date
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Add parent directory to path for Vercel serverless environment
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from jewcal import JewCal
from redis_client import get_users_with_shabbat_reminders_enabled, get_user_prefs
from telegram_bot import send_photo, send_message, download_photo, CITY_BY_NAME
from api.poster import build_poster_from_payload

# Vercel cron secret for authentication
CRON_SECRET = os.environ.get("CRON_SECRET")


def is_friday_or_erev_yomtov() -> bool:
    """
    Check if today is Friday or Erev Yom Tov (eve of a holiday).
    
    Returns:
        bool: True if today is Friday or the eve of a Jewish holiday
    """
    today = date.today()
    
    # Check if it's Friday (weekday 4 = Friday, 0 = Monday)
    if today.weekday() == 4:
        return True
    
    # Check if it's Erev Yom Tov using jewcal
    jewcal_obj = JewCal(gregorian_date=today, diaspora=False)
    
    if jewcal_obj.has_events():
        # Check if this is Erev (eve of) a holiday - indicated by "Candles" action
        if jewcal_obj.events.action == "Candles" and jewcal_obj.events.yomtov:
            return True
    
    return False


def send_shabbat_reminder(user_id: str) -> bool:
    """
    Send Shabbat/Holiday reminder poster to a single user.

    Args:
        user_id: Telegram user ID (also used as chat_id for private chats)

    Returns:
        bool: True if sent successfully, False otherwise
    """
    try:
        # Get user preferences
        prefs = get_user_prefs(user_id)
        chat_id = int(user_id)

        # Build payload for Shabbat poster (not Omer mode)
        payload = {
            "omerMode": False,
            "dateFormat": prefs.get("date_format", "both"),
        }

        # Add cities if defined
        cities = prefs.get("cities")
        if cities:
            mapped_cities = []
            for city in cities:
                name = city.get("name") if isinstance(city, dict) else city
                offset = city.get("candle_offset", 20) if isinstance(city, dict) else 20
                if name in CITY_BY_NAME:
                    full_city = CITY_BY_NAME[name].copy()
                    full_city["candle_offset"] = offset
                    mapped_cities.append(full_city)
            if mapped_cities:
                payload["cities"] = mapped_cities

        # Add blessing text if defined
        blessing = prefs.get("blessing_text")
        if blessing:
            payload["message"] = blessing

        # Add dedication text if defined
        dedication = prefs.get("dedication_text")
        if dedication:
            payload["leiluyNeshama"] = dedication

        # Check if user has a saved Shabbat image (fallback to general image)
        saved_file_id = prefs.get("shabbat_image_file_id") or prefs.get("last_image_file_id")
        if saved_file_id:
            photo_bytes = download_photo(saved_file_id)
            if photo_bytes:
                payload["imageBase64"] = base64.b64encode(photo_bytes).decode("utf-8")

        # Generate poster
        poster_bytes = build_poster_from_payload(payload)

        # Send to user
        result = send_photo(chat_id, poster_bytes, "🕯️ שבת שלום! הנה הפוסטר שלך לשבת/חג")

        return result.get("ok", False)

    except Exception as e:
        print(f"Error sending Shabbat reminder to user {user_id}: {e}")
        return False


class handler(BaseHTTPRequestHandler):
    """Vercel serverless function entrypoint for Shabbat reminder cron."""

    def do_GET(self):
        """Handle GET request from Vercel Cron or manual test."""
        # Parse query parameters first to check for test mode
        parsed_url = urlparse(self.path)
        query_params = parse_qs(parsed_url.query)

        # Check for test_user_id parameter (for manual testing)
        test_user_id = query_params.get("test_user_id", [None])[0]

        # Skip auth for test mode, require cron secret for production requests
        if not test_user_id:
            # Verify cron secret if configured
            if CRON_SECRET:
                auth_header = self.headers.get("Authorization")
                if auth_header != f"Bearer {CRON_SECRET}":
                    self.send_response(401)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(b'{"error": "Unauthorized"}')
                    return

        try:
            if test_user_id:
                # Manual test mode: send reminder to specific user regardless of day
                success = send_shabbat_reminder(test_user_id)
                response = {
                    "status": "test_completed",
                    "test_user_id": test_user_id,
                    "sent": 1 if success else 0,
                    "failed": 0 if success else 1,
                }
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps(response, ensure_ascii=False).encode("utf-8"))
                return

            # Normal cron mode: check if it's Friday or Erev Yom Tov
            if not is_friday_or_erev_yomtov():
                response = {
                    "status": "skipped",
                    "reason": "Not Friday or Erev Yom Tov",
                    "sent": 0,
                    "failed": 0,
                }
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps(response, ensure_ascii=False).encode("utf-8"))
                return

            # Get all users with Shabbat reminders enabled
            users = get_users_with_shabbat_reminders_enabled()

            sent_count = 0
            failed_count = 0

            for user_id in users:
                if send_shabbat_reminder(user_id):
                    sent_count += 1
                else:
                    failed_count += 1

            response = {
                "status": "completed",
                "sent": sent_count,
                "failed": failed_count,
                "total_users": len(users),
            }

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(response, ensure_ascii=False).encode("utf-8"))

        except Exception as e:
            print(f"Shabbat reminder cron error: {e}")
            error_response = {"error": str(e)}
            self.send_response(500)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(error_response, ensure_ascii=False).encode("utf-8"))

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass

