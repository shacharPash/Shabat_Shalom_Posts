"""Authenticated GitHub Actions reminder endpoint. Targeted calls retain all guards."""

import base64
import os
import sys
from datetime import datetime
from http.server import BaseHTTPRequestHandler

# Add parent directory to path for Vercel serverless environment
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from reminder_delivery import run_reminders

from jewcal import JewCal
from omer_utils import ISRAEL_TZ
from redis_client import get_user_prefs
from telegram_bot import send_photo_with_keyboard, download_photo, CITY_BY_NAME, _build_shabbat_poster_keyboard
from api.poster import build_poster_from_payload

# Vercel cron secret for authentication
CRON_SECRET = os.environ.get("CRON_SECRET")


def is_friday_or_erev_yomtov(now=None) -> bool:
    """
    Check if today is Friday or Erev Yom Tov (eve of a holiday).
    
    Returns:
        bool: True if today is Friday or the eve of a Jewish holiday
    """
    today = now.date() if now else datetime.now(ISRAEL_TZ).date()
    
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


def send_shabbat_reminder(user_id: str, context: dict | None = None) -> bool:
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
            "startDate": context["now"].date().isoformat() if context else datetime.now(ISRAEL_TZ).date().isoformat(),
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

        # Send to user with main menu keyboard
        keyboard = _build_shabbat_poster_keyboard()
        result = send_photo_with_keyboard(chat_id, poster_bytes, "🕯️ שבת שלום! הנה הפוסטר שלך לשבת/חג", keyboard)

        return result.get("ok", False)

    except Exception:
        return False


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        run_reminders(self, CRON_SECRET, 'shabbat', send_shabbat_reminder, is_friday_or_erev_yomtov)

    def log_message(self, format, *args):
        pass
