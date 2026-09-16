"""
Telegram webhook endpoint for Vercel serverless deployment.

Receives POST requests from Telegram and routes them to the bot handlers.
"""

import json
import os
import secrets
import sys
from http.server import BaseHTTPRequestHandler

# Add parent directory to path for Vercel serverless environment
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from telegram_bot import process_update, UpdateRateLimited

# Telegram supplies this value in X-Telegram-Bot-Api-Secret-Token when the
# webhook is registered with secret_token. Fail closed when it is missing.
TELEGRAM_WEBHOOK_SECRET = os.environ.get("TELEGRAM_WEBHOOK_SECRET")
MAX_UPDATE_BYTES = 1_000_000


def is_valid_webhook_secret(provided: str | None) -> bool:
    """Validate Telegram's webhook token without leaking timing information."""
    return bool(
        TELEGRAM_WEBHOOK_SECRET
        and provided
        and secrets.compare_digest(provided.encode(), TELEGRAM_WEBHOOK_SECRET.encode())
    )


class handler(BaseHTTPRequestHandler):
    """Vercel serverless function entrypoint for Telegram webhook."""

    def do_POST(self):
        """Handle POST request from Telegram."""
        if not TELEGRAM_WEBHOOK_SECRET:
            self._send_json(503, b'{"ok": false, "error": "unavailable"}')
            return

        secret_header = self.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if not is_valid_webhook_secret(secret_header):
            self._send_json(403, b'{"ok": false, "error": "forbidden"}')
            return

        try:
            # Read request body
            try:
                content_length = int(self.headers.get("Content-Length", 0))
            except (TypeError, ValueError):
                self._send_json(400, b'{"ok": false, "error": "invalid content length"}')
                return
            if content_length < 0 or content_length > MAX_UPDATE_BYTES:
                self._send_json(413, b'{"ok": false, "error": "update is too large"}')
                return
            body = self.rfile.read(content_length) if content_length > 0 else b""

            if not body:
                self._send_json(400, b'{"ok": false, "error": "invalid update"}')
                return
            try:
                update = json.loads(body.decode("utf-8"))
                from telegram_bot import _validate_update
                _validate_update(update)
            except (ValueError, TypeError):
                self._send_json(400, b'{"ok": false, "error": "invalid update"}')
                return
            process_update(update)
            self._send_json(200, b'{"ok": true}')
        except UpdateRateLimited:
            self._send_json(429, b'{"ok": false, "error": "rate limited"}', retry_after="60")
        except Exception:
            print('{"event":"webhook","failed":1}')
            self._send_json(503, b'{"ok": false, "error": "unavailable"}', retry_after="30")

    def _send_json(self, status: int, body: bytes, retry_after: str | None = None):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if retry_after:
            self.send_header("Retry-After", retry_after)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        """Handle GET request - health check."""
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status": "ok", "service": "telegram-webhook"}')

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass
