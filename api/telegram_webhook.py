"""
Telegram webhook endpoint for Vercel serverless deployment.

Receives POST requests from Telegram and routes them to the bot handlers.
"""

import json
import os
import sys
from http.server import BaseHTTPRequestHandler

# Add parent directory to path for Vercel serverless environment
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from telegram_bot import process_update


class handler(BaseHTTPRequestHandler):
    """Vercel serverless function entrypoint for Telegram webhook."""

    def do_POST(self):
        """Handle POST request from Telegram."""
        try:
            # Read request body
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length) if content_length > 0 else b""

            # Parse JSON update
            if body:
                update = json.loads(body.decode("utf-8"))
                
                # Process the update
                process_update(update)

            # Always return 200 OK to Telegram
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok": true}')

        except json.JSONDecodeError as e:
            # Still return 200 to avoid Telegram retries
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok": true, "error": "invalid json"}')

        except Exception as e:
            # Log error but still return 200 to avoid Telegram retries
            print(f"Webhook error: {e}")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok": true, "error": "internal error"}')

    def do_GET(self):
        """Handle GET request - health check."""
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status": "ok", "service": "telegram-webhook"}')

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass

