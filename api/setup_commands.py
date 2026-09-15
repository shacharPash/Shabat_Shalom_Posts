"""
Telegram bot command menu setup endpoint.

GET or POST to /api/setup_commands to register the bot's command menu.
This sets the commands that appear when users press / in the Telegram chat.
"""

import os
import sys
from http.server import BaseHTTPRequestHandler

# Add parent directory to path for Vercel serverless environment
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from telegram_bot import set_bot_commands
from bot_auth import authenticate_cron, send_json
CRON_SECRET = os.environ.get("CRON_SECRET")


class handler(BaseHTTPRequestHandler):
    """Vercel serverless function for setting up bot commands."""

    def _setup_commands(self):
        """Call set_bot_commands and return appropriate response."""
        if not authenticate_cron(self, CRON_SECRET):
            return
        try:
            result = set_bot_commands()
            send_json(self, 200 if result.get('ok') else 503, {'ok': bool(result.get('ok'))})
        except Exception:
            send_json(self, 503, {'ok': False, 'error': 'unavailable'})

    def log_message(self, format, *args):
        pass

    def do_GET(self):
        """Handle GET request - setup commands."""
        self._setup_commands()

    def do_POST(self):
        """Handle POST request - setup commands."""
        self._setup_commands()

