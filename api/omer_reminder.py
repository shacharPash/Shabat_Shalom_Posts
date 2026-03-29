"""
Vercel Cron endpoint for daily Omer reminders.

Runs at 15:00 UTC (18:00 Israel summer time / 17:00 winter time) - after tzet hakochavim.
Sends Omer poster to all users with reminder_enabled=True.
"""

import json
import os
import sys
from datetime import date
from http.server import BaseHTTPRequestHandler

# Add parent directory to path for Vercel serverless environment
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from omer_utils import get_omer_day
from redis_client import get_users_with_reminders_enabled, get_user_prefs
from telegram_bot import send_photo, send_message, CITY_BY_NAME
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
    Send Omer poster to a single user.
    
    Args:
        user_id: Telegram user ID (also used as chat_id for private chats)
        
    Returns:
        bool: True if sent successfully, False otherwise
    """
    try:
        # Get user preferences
        prefs = get_user_prefs(user_id)
        
        # Build payload for Omer poster
        payload = {
            "omerMode": True,
            "dateFormat": prefs.get("date_format", "both"),
            "nusach": prefs.get("nusach", "sefard"),
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
        
        # Generate poster
        poster_bytes = build_poster_from_payload(payload)
        
        # Send to user (user_id is chat_id for private chats)
        chat_id = int(user_id)
        result = send_photo(chat_id, poster_bytes, "🔢 תזכורת יומית לספירת העומר!")
        
        return result.get("ok", False)
        
    except Exception as e:
        print(f"Error sending reminder to user {user_id}: {e}")
        return False


class handler(BaseHTTPRequestHandler):
    """Vercel serverless function entrypoint for Omer reminder cron."""

    def do_GET(self):
        """Handle GET request from Vercel Cron."""
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
            # Check if we're in the Omer period
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

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass

