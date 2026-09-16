"""Serve assets contained in the public directory, including legacy aliases."""
import mimetypes
from pathlib import Path, PurePosixPath
from urllib.parse import unquote
from http.server import BaseHTTPRequestHandler

PUBLIC_DIR = Path(__file__).resolve().parents[1] / "public"
STATIC_DIR = str(PUBLIC_DIR)


def resolve_static_path(request_path):
    path = request_path.split("?", 1)[0]
    # Decode nested encodings before checking containment. Reject any leftover
    # encoding rather than allowing another layer to reinterpret it later.
    for _ in range(8):
        decoded = unquote(path)
        if decoded == path:
            break
        path = decoded
    if "%" in path or "\\" in path or "\0" in path:
        raise ValueError("Invalid asset path")
    for prefix in ("/api/static/", "/static/", "/"):
        if path.startswith(prefix):
            path = path[len(prefix):]
            break
    relative = PurePosixPath(path)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Invalid asset path")
    resolved = (PUBLIC_DIR / path).resolve()
    if not resolved.is_relative_to(PUBLIC_DIR.resolve()):
        raise ValueError("Invalid asset path")
    return resolved


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            file_path = resolve_static_path(self.path)
        except ValueError:
            self.send_error(403, "Forbidden")
            return
        if not file_path.is_file():
            self.send_error(404, "File not found")
            return
        try:
            content = file_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", mimetypes.guess_type(file_path)[0] or "application/octet-stream")
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "public, max-age=86400")
            self.end_headers()
            self.wfile.write(content)
        except OSError:
            self.send_error(500, "Internal Server Error")
