from http.server import BaseHTTPRequestHandler
import json


class handler(BaseHTTPRequestHandler):
    """Simple test endpoint."""

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status": "ok", "method": "GET"}')

    def do_POST(self):
        # Read body
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else b""
        
        # Send response
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        response = {"status": "ok", "method": "POST", "received_bytes": len(body)}
        self.wfile.write(json.dumps(response).encode("utf-8"))

