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

from telegram_bot import process_update
from rate_limiter import RateLimiter

# Telegram supplies this value in X-Telegram-Bot-Api-Secret-Token when the
# webhook is registered with secret_token. Fail closed when it is missing.
TELEGRAM_WEBHOOK_SECRET = os.environ.get("TELEGRAM_WEBHOOK_SECRET")
MAX_UPDATE_BYTES = 1_000_000

# Rate limiter: 30 requests per minute per IP
_rate_limiter = RateLimiter(max_requests=30, window_seconds=60)


def is_valid_webhook_secret(provided: str | None) -> bool:
    """Validate Telegram's webhook token without leaking timing information."""
    return bool(
        TELEGRAM_WEBHOOK_SECRET
        and provided
        and secrets.compare_digest(provided, TELEGRAM_WEBHOOK_SECRET)
    )


class handler(BaseHTTPRequestHandler):
    """Vercel serverless function entrypoint for Telegram webhook."""

    def _get_client_ip(self) -> str:
        """Extract client IP from request headers."""
        # Check X-Forwarded-For header (set by Vercel/proxies)
        forwarded_for = self.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take the first IP in the chain (original client)
            return forwarded_for.split(",")[0].strip()

        # Check X-Real-IP header
        real_ip = self.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()

        # Fall back to client address
        return self.client_address[0] if self.client_address else "unknown"

    def do_POST(self):
        """Handle POST request from Telegram."""
        if not TELEGRAM_WEBHOOK_SECRET:
            self._send_json(503, b'{"ok": false, "error": "webhook secret is not configured"}')
            return

        secret_header = self.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if not is_valid_webhook_secret(secret_header):
            self._send_json(403, b'{"ok": false, "error": "forbidden"}')
            return

        # Rate limiting check
        client_ip = self._get_client_ip()
        is_allowed, remaining = _rate_limiter.check(client_ip)

        if not is_allowed:
            self._send_json(429, b'{"error": "Rate limit exceeded. Try again later."}', retry_after="60")
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

            # Parse JSON update
            if body:
                update = json.loads(body.decode("utf-8"))

                # Process the update
                process_update(update)

            # Always return 200 OK to Telegram
            self._send_json(200, b'{"ok": true}')

        except json.JSONDecodeError as e:
            # Still return 200 to avoid Telegram retries
            print(f"Telegram webhook JSON decode error: {e}")  # Log full details
            self._send_json(200, b'{"ok": true}')

        except Exception as e:
            # Log error but still return 200 to avoid Telegram retries
            print(f"Telegram webhook error: {e}")  # Log full details
            self._send_json(200, b'{"ok": true}')

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
