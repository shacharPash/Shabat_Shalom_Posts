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
from rate_limiter import RateLimiter

# Load webhook secret for validation (optional - for backward compatibility)
TELEGRAM_WEBHOOK_SECRET = os.environ.get("TELEGRAM_WEBHOOK_SECRET")

# Rate limiter: 30 requests per minute per IP
_rate_limiter = RateLimiter(max_requests=30, window_seconds=60)


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
        # Rate limiting check
        client_ip = self._get_client_ip()
        is_allowed, remaining = _rate_limiter.check(client_ip)

        if not is_allowed:
            error_body = b'{"error": "Rate limit exceeded. Try again later."}'
            self.send_response(429)
            self.send_header("Content-Type", "application/json")
            self.send_header("Retry-After", "60")
            self.end_headers()
            self.wfile.write(error_body)
            return

        # Validate webhook secret if configured
        if TELEGRAM_WEBHOOK_SECRET:
            secret_header = self.headers.get("X-Telegram-Bot-Api-Secret-Token")
            if secret_header != TELEGRAM_WEBHOOK_SECRET:
                self.send_response(403)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"ok": false, "error": "forbidden"}')
                return

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

