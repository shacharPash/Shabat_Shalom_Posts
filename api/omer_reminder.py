"""Authenticated GitHub Actions reminder endpoint. Targeted calls retain all guards."""

import base64
import os
import sys
from datetime import datetime
from http.server import BaseHTTPRequestHandler

# Add parent directory to path for Vercel serverless environment
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from reminder_delivery import run_reminders

from omer_utils import get_omer_day, get_omer_count_text, get_sefirah_text, ISRAEL_TZ, omer_event_context
from redis_client import get_user_prefs
from telegram_bot import send_message_with_keyboard, send_photo_with_keyboard, download_photo, CITY_BY_NAME, _build_omer_poster_keyboard
from api.poster import build_poster_from_payload

# Vercel cron secret for authentication
CRON_SECRET = os.environ.get("CRON_SECRET")


def is_omer_period() -> bool:
    """Check if we're currently in the Omer period."""
    now_israel = datetime.now(ISRAEL_TZ)
    omer_day = get_omer_day(now_israel)
    return omer_day is not None and 1 <= omer_day <= 49


def send_omer_reminder(user_id: str, context: dict | None = None) -> bool:
    """
    Send Omer reminder to a single user (text or image based on preference).

    Args:
        user_id: Telegram user ID (also used as chat_id for private chats)

    Returns:
        bool: True if sent successfully, False otherwise
    """
    try:
        context = context or omer_event_context()
        # Get user preferences
        prefs = get_user_prefs(user_id)
        nusach = prefs.get("nusach", "sefard")
        reminder_type = prefs.get("reminder_type", "image")

        chat_id = int(user_id)

        # Check reminder type preference
        if reminder_type == "text":
            # Send text-only reminder
            return _send_text_reminder(chat_id, nusach, context)
        else:
            # Send image reminder (default)
            return _send_image_reminder(chat_id, prefs, nusach, context)

    except Exception:
        return False


def _send_text_reminder(chat_id: int, nusach: str, context: dict | None = None) -> bool:
    """
    Send text-only Omer reminder with the counting text.

    Args:
        chat_id: Telegram chat ID
        nusach: User's nusach preference (sefard, ashkenaz, edot_hamizrach)

    Returns:
        bool: True if sent successfully, False otherwise
    """
    context = context or omer_event_context()
    omer_day = context["day"]

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

    result = send_message_with_keyboard(chat_id, message, _build_omer_poster_keyboard(context), parse_mode="Markdown")
    return result.get("ok", False)


def _send_image_reminder(chat_id: int, prefs: dict, nusach: str, context: dict | None = None) -> bool:
    """
    Send image (poster) Omer reminder.

    Args:
        chat_id: Telegram chat ID
        prefs: User preferences dict
        nusach: User's nusach preference

    Returns:
        bool: True if sent successfully, False otherwise
    """
    context = context or omer_event_context()
    # Build payload for Omer poster
    payload = {
        "omerMode": True,
        "omerDay": context["day"],
        "omerDate": context["date"].isoformat(),
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

    # Check if user has a saved Omer image (no fallback - last_image_file_id is for Shabbat posters)
    saved_file_id = prefs.get("omer_image_file_id")
    if saved_file_id:
        photo_bytes = download_photo(saved_file_id)
        if photo_bytes:
            payload["imageBase64"] = base64.b64encode(photo_bytes).decode("utf-8")

    # Generate poster
    poster_bytes = build_poster_from_payload(payload)

    # Send to user with "ספרתי" keyboard
    keyboard = _build_omer_poster_keyboard(context)
    result = send_photo_with_keyboard(chat_id, poster_bytes, "🔢 תזכורת יומית לספירת העומר!", keyboard)

    return result.get("ok", False)


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        run_reminders(self, CRON_SECRET, 'evening', send_omer_reminder)

    def log_message(self, format, *args):
        pass
