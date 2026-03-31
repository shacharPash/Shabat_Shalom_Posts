"""
Vercel Cron endpoint for daily Omer reminders.

Runs at 15:00 UTC (18:00 Israel summer time / 17:00 winter time) - after tzet hakochavim.
Sends Omer poster to all users with reminder_enabled=True.

Query Parameters:
    test_user_id: (optional) Send reminder to specific user for testing.
                  Bypasses the Omer period check. Example: ?test_user_id=123456789
"""

import base64
import json
import os
import sys
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Add parent directory to path for Vercel serverless environment
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from omer_utils import get_omer_day, get_omer_count_text, get_sefirah_text, get_omer_info_for_time, ISRAEL_TZ
from redis_client import get_users_with_reminders_enabled, get_user_prefs, mark_omer_sent_today, was_omer_sent_today
from telegram_bot import send_photo, send_message, download_photo, CITY_BY_NAME
from api.poster import build_poster_from_payload

# Vercel cron secret for authentication
CRON_SECRET = os.environ.get("CRON_SECRET")


def is_omer_period() -> bool:
    """Check if we're currently in the Omer period."""
    today = date.today()
    omer_day = get_omer_day(today)
    return omer_day is not None and 1 <= omer_day <= 49


def send_omer_reminder(user_id: str) -> bool:
    """
    Send Omer reminder to a single user (text or image based on preference).

    Args:
        user_id: Telegram user ID (also used as chat_id for private chats)

    Returns:
        bool: True if sent successfully, False otherwise
    """
    try:
        # Get user preferences
        prefs = get_user_prefs(user_id)
        nusach = prefs.get("nusach", "sefard")
        reminder_type = prefs.get("reminder_type", "image")

        chat_id = int(user_id)

        # Check reminder type preference
        if reminder_type == "text":
            # Send text-only reminder
            return _send_text_reminder(chat_id, nusach)
        else:
            # Send image reminder (default)
            return _send_image_reminder(chat_id, prefs, nusach)

    except Exception as e:
        print(f"Error sending reminder to user {user_id}: {e}")
        return False


def _send_text_reminder(chat_id: int, nusach: str) -> bool:
    """
    Send text-only Omer reminder with the counting text.

    Args:
        chat_id: Telegram chat ID
        nusach: User's nusach preference (sefard, ashkenaz, edot_hamizrach)

    Returns:
        bool: True if sent successfully, False otherwise
    """
    today = date.today()
    omer_day = get_omer_day(today)

    if not omer_day or omer_day < 1 or omer_day > 49:
        return False

    # Get the Hebrew counting text
    count_text = get_omer_count_text(omer_day, nusach)
    sefirah_text = get_sefirah_text(omer_day)

    # Build the text message
    message = f"🔢 *תזכורת לספירת העומר*\n\n"
    message += f"📅 יום {omer_day} לעומר\n\n"
    message += f"🕯️ {count_text}\n\n"
    message += f"✨ {sefirah_text}"

    result = send_message(chat_id, message, parse_mode="Markdown")
    return result.get("ok", False)


def _send_image_reminder(chat_id: int, prefs: dict, nusach: str) -> bool:
    """
    Send image (poster) Omer reminder.

    Args:
        chat_id: Telegram chat ID
        prefs: User preferences dict
        nusach: User's nusach preference

    Returns:
        bool: True if sent successfully, False otherwise
    """
    # Build payload for Omer poster
    payload = {
        "omerMode": True,
        "dateFormat": prefs.get("date_format", "both"),
        "nusach": nusach,
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

    # Check if user has a saved Omer image (fallback to general image)
    saved_file_id = prefs.get("omer_image_file_id") or prefs.get("last_image_file_id")
    if saved_file_id:
        photo_bytes = download_photo(saved_file_id)
        if photo_bytes:
            payload["imageBase64"] = base64.b64encode(photo_bytes).decode("utf-8")

    # Generate poster
    poster_bytes = build_poster_from_payload(payload)

    # Send to user
    result = send_photo(chat_id, poster_bytes, "🔢 תזכורת יומית לספירת העומר!")

    return result.get("ok", False)


class handler(BaseHTTPRequestHandler):
    """Vercel serverless function entrypoint for Omer reminder cron."""

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
                # Manual test mode: send reminder to specific user regardless of Omer period
                success = send_omer_reminder(test_user_id)
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

            # Check for check_sunset parameter (sunset-based reminder mode)
            check_sunset = query_params.get("check_sunset", [None])[0]

            if check_sunset == "true":
                # Sunset-based reminder mode: check if after tzet hakochavim
                response = self._handle_sunset_check()
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps(response, ensure_ascii=False).encode("utf-8"))
                return

            # Normal cron mode: check if we're in the Omer period
            if not is_omer_period():
                response = {
                    "status": "skipped",
                    "reason": "Not in Omer period",
                    "sent": 0,
                    "failed": 0,
                }
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps(response, ensure_ascii=False).encode("utf-8"))
                return

            # Get all users with reminders enabled
            users = get_users_with_reminders_enabled()

            sent_count = 0
            failed_count = 0

            for user_id in users:
                if send_omer_reminder(user_id):
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
            print(f"Omer reminder cron error: {e}")
            error_response = {"error": str(e)}
            self.send_response(500)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(error_response, ensure_ascii=False).encode("utf-8"))

    def _handle_sunset_check(self) -> dict:
        """
        Handle sunset-based reminder check.

        Only sends reminders if:
        1. Currently after tzet hakochavim (sunset)
        2. We're in the Omer period
        3. Reminder hasn't been sent today for this user

        Returns:
            dict: Response with status and counts
        """
        # Get current time in Israel timezone
        now_israel = datetime.now(ISRAEL_TZ)
        today = now_israel.date()
        current_hour = now_israel.hour
        current_minute = now_israel.minute
        today_str = today.isoformat()

        # Get Omer info for current time
        omer_info = get_omer_info_for_time(today, current_hour, current_minute)

        # Check if we're in Omer period
        if not omer_info.get("isOmerPeriod", False):
            return {
                "status": "skipped",
                "reason": "Not in Omer period",
                "sent": 0,
                "failed": 0,
                "skipped": 0,
            }

        # Check if after sunset (tzet hakochavim)
        is_after_sunset = omer_info.get("isAfterSunset", False)
        if not is_after_sunset:
            return {
                "status": "skipped",
                "reason": "Before tzet hakochavim",
                "current_time": f"{current_hour:02d}:{current_minute:02d}",
                "tzet_time": omer_info.get("tzetTime"),
                "sent": 0,
                "failed": 0,
                "skipped": 0,
            }

        # Get all users with reminders enabled
        users = get_users_with_reminders_enabled()

        sent_count = 0
        failed_count = 0
        skipped_count = 0

        for user_id in users:
            # Check if already sent today
            if was_omer_sent_today(user_id, today_str):
                skipped_count += 1
                continue

            # Send reminder
            if send_omer_reminder(user_id):
                # Mark as sent to prevent duplicates
                mark_omer_sent_today(user_id, today_str)
                sent_count += 1
            else:
                failed_count += 1

        return {
            "status": "completed",
            "mode": "sunset_check",
            "current_time": f"{current_hour:02d}:{current_minute:02d}",
            "tzet_time": omer_info.get("tzetTime"),
            "omer_day": omer_info.get("posterDay"),
            "sent": sent_count,
            "failed": failed_count,
            "skipped": skipped_count,
            "total_users": len(users),
        }

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass

