"""
Telegram bot command menu setup endpoint.

GET or POST to /api/setup_commands to register the bot's command menu.
This sets the commands that appear when users press / in the Telegram chat.
"""

import json
import os
import sys
from http.server import BaseHTTPRequestHandler

# Add parent directory to path for Vercel serverless environment
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from telegram_bot import set_bot_commands


class handler(BaseHTTPRequestHandler):
    """Vercel serverless function for setting up bot commands."""

    def _setup_commands(self):
        """Call set_bot_commands and return appropriate response."""
        try:
            result = set_bot_commands()
            
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            
            response = {
                "ok": result.get("ok", False),
                "message": "Commands registered successfully" if result.get("ok") else "Failed to register commands",
                "telegram_response": result,
            }
            self.wfile.write(json.dumps(response, ensure_ascii=False).encode("utf-8"))
            
        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            response = {"ok": False, "error": str(e)}
            self.wfile.write(json.dumps(response).encode("utf-8"))

    def do_GET(self):
        """Handle GET request - setup commands."""
        self._setup_commands()

    def do_POST(self):
        """Handle POST request - setup commands."""
        self._setup_commands()

