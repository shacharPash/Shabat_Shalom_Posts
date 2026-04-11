"""
Vercel Cron endpoint for morning Omer reminders.

Runs at 6:00 UTC (9:00 Israel summer time).
Sends a reminder to users who didn't mark that they counted the Omer last night.

Query Parameters:
    test_user_id: (optional) Send reminder to specific user for testing.
                  Bypasses the Omer period check. Example: ?test_user_id=123456789
"""

import json
import os
import sys
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Add parent directory to path for Vercel serverless environment
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from omer_utils import get_omer_day, ISRAEL_TZ
from redis_client import get_users_with_reminders_enabled, was_omer_counted
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
    now_israel = datetime.now(ISRAEL_TZ)
    
    # In the morning, we check for the previous evening's count
    # Since Omer day changes at nightfall, we need to get yesterday's evening time
    # to calculate what day they should have counted
    yesterday_evening = now_israel.replace(hour=20, minute=0) - timedelta(days=1)
    
    return get_omer_day(yesterday_evening)


def send_morning_reminder(user_id: str, omer_day: int) -> bool:
    """
    Send morning reminder to a user who didn't mark that they counted.
    
    Args:
        user_id: Telegram user ID
        omer_day: The Omer day they should have counted
        
    Returns:
        bool: True if sent successfully, False otherwise
    """
    try:
        chat_id = int(user_id)
        
        message = f"🌅 לא סימנת שספרת יום {omer_day} לעומר.\n\n"
        message += "אפשר לספור עכשיו בלי ברכה."
        
        result = send_message(chat_id, message)
        return result.get("ok", False)
        
    except Exception as e:
        print(f"Error sending morning reminder to user {user_id}: {e}")
        return False


class handler(BaseHTTPRequestHandler):
    """Vercel serverless function entrypoint for Omer morning reminder cron."""

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

        # Test mode: send to specific user
        if test_user_id:
            # For testing, use a test Omer day
            test_omer_day = int(query_params.get("omer_day", [1])[0])
            success = send_morning_reminder(test_user_id, test_omer_day)
            response = {
                "status": "test",
                "user_id": test_user_id,
                "omer_day": test_omer_day,
                "sent": success,
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(response, ensure_ascii=False).encode("utf-8"))
            return

        # Get last night's Omer day
        omer_day = get_last_night_omer_day()
        
        if omer_day is None:
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
        skipped_count = 0

        for user_id in users:
            # Check if user marked that they counted this Omer day
            if was_omer_counted(user_id, omer_day):
                skipped_count += 1
                continue
            
            # User didn't mark counting - send reminder
            if send_morning_reminder(user_id, omer_day):
                sent_count += 1
            else:
                failed_count += 1

        response = {
            "status": "completed",
            "omer_day": omer_day,
            "sent": sent_count,
            "failed": failed_count,
            "skipped": skipped_count,
            "total_users": len(users),
        }

        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(response, ensure_ascii=False).encode("utf-8"))

