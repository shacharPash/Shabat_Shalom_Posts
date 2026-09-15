"""Authenticated GitHub Actions reminder endpoint. Targeted calls retain all guards."""

import os
import sys
from datetime import datetime
from http.server import BaseHTTPRequestHandler

# Add parent directory to path for Vercel serverless environment
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from reminder_delivery import run_reminders

from omer_utils import get_omer_day, ISRAEL_TZ, omer_event_context
from telegram_bot import send_message

# Vercel cron secret for authentication
CRON_SECRET = os.environ.get("CRON_SECRET")


def get_last_night_omer_day() -> int | None:
    """
    Get the Omer day that should have been counted last night.
    
    At 9:00 AM, we want to check if the user counted LAST NIGHT.
    Last night's Omer day = today's morning Omer day (since the day starts at nightfall).
    
    Returns:
        The Omer day (1-49) or None if not in Omer period.
    """
    return omer_event_context()["day"]


def send_morning_reminder(user_id: str, context: dict) -> bool:
    """
    Send morning reminder to a user who didn't mark that they counted.
    
    Args:
        user_id: Telegram user ID
        omer_day: The Omer day they should have counted
        
    Returns:
        bool: True if sent successfully, False otherwise
    """
    try:
        omer_day = context["day"]
        chat_id = int(user_id)
        
        message = f"🌅 לא סימנת שספרת יום {omer_day} לעומר.\n\n"
        message += "אפשר לספור עכשיו בלי ברכה."
        
        result = send_message(chat_id, message)
        return result.get("ok", False)
        
    except Exception:
        return False


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        run_reminders(self, CRON_SECRET, 'morning', send_morning_reminder)

    def log_message(self, format, *args):
        pass
