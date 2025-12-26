"""
Serve static files from the public/static directory.
This endpoint handles /static/* requests for local development.
On Vercel, files in public/ are served automatically.
"""

import os
import mimetypes
from http.server import BaseHTTPRequestHandler

# Static files directory
STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "public", "static")


class handler(BaseHTTPRequestHandler):
    """Serve static files."""

    def do_GET(self):
        # Get the requested file path (remove /static/ prefix if present)
        path = self.path.split("?")[0]  # Remove query string
        if path.startswith("/static/"):
            path = path[8:]  # Remove "/static/" prefix
        elif path.startswith("/api/static/"):
            path = path[12:]  # Remove "/api/static/" prefix
        elif path.startswith("/"):
            path = path[1:]  # Remove leading slash

        # Security: prevent directory traversal
        if ".." in path:
            self.send_error(403, "Forbidden")
            return

        file_path = os.path.join(STATIC_DIR, path)

        if not os.path.isfile(file_path):
            self.send_error(404, "File not found")
            return

        try:
            # Determine content type
            content_type, _ = mimetypes.guess_type(file_path)
            if content_type is None:
                content_type = "application/octet-stream"

            # Read and send file
            with open(file_path, "rb") as f:
                content = f.read()

            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "public, max-age=86400")  # Cache for 1 day
            self.end_headers()
            self.wfile.write(content)

        except Exception as e:
            self.send_error(500, f"Internal Server Error: {e}")

