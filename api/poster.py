import base64
import json
import os
import tempfile
from datetime import date
from http.server import BaseHTTPRequestHandler
from typing import Any, Dict, List, Optional

import requests

from make_shabbat_posts import generate_poster, CITIES


def build_poster_from_payload(payload: Dict[str, Any]) -> bytes:
    """
    Pure logic function that:
    - Receives a dict representing the JSON payload of a request
    - Returns PNG bytes for a single generated poster.

    Expected payload structure (all fields optional):
    {
      "imageBase64": "...",                 # base64-encoded PNG/JPEG (highest priority)
      "imageUrl": "https://...",            # URL to download image from
      "image": "images/example.jpg",        # path to background image (local)
      "message": "שבת שלום לכולם!",        # bottom blessing text
      "leiluyNeshama": "אורי בורנשטיין",  # dedication name
      "cities": [                          # override default CITIES
        { "name": "...", "lat": ..., "lon": ..., "candle_offset": ... }
      ],
      "startDate": "YYYY-MM-DD",           # base date for calculations
      "dateFormat": "gregorian"            # "gregorian", "hebrew", or "both"
    }

    Priority for background image:
    1. imageBase64 (if provided)
    2. imageUrl (if provided)
    3. image (local path, if provided)
    4. Fallback: first image from images/ folder
    """

    image_base64: Optional[str] = payload.get("imageBase64")
    image_url: Optional[str] = payload.get("imageUrl")
    image_path: Optional[str] = payload.get("image")
    message: Optional[str] = payload.get("message")
    leiluy_neshama: Optional[str] = payload.get("leiluyNeshama")
    hide_dedication: bool = payload.get("hideDedication", False)
    hide_blessing: bool = payload.get("hideBlessing", False)
    cities: Optional[List[Dict[str, Any]]] = payload.get("cities")
    date_format: str = payload.get("dateFormat", "gregorian")  # "gregorian", "hebrew", or "both"

    start_date_str: Optional[str] = payload.get("startDate")
    if start_date_str:
        start_date = date.fromisoformat(start_date_str)
    else:
        start_date = None

    # Priority 1: imageBase64
    if image_base64:
        try:
            image_bytes = base64.b64decode(image_base64)
            # Save to a temporary file (cloud-safe: uses /tmp)
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
            tmp.write(image_bytes)
            tmp.close()
            image_path = tmp.name
        except Exception as e:
            raise RuntimeError(f"Failed to decode imageBase64: {e}")

    # Priority 2: imageUrl
    elif image_url:
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            r = requests.get(image_url, timeout=15, headers=headers)
            if r.status_code != 200:
                raise RuntimeError("Failed to download image from imageUrl")
            # Save to a temporary file (cloud-safe: uses /tmp)
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
            tmp.write(r.content)
            tmp.close()
            image_path = tmp.name
        except requests.RequestException as e:
            raise RuntimeError(f"Failed to download image from imageUrl: {e}")

    # Priority 3: image (local path) - already set from payload.get("image")
    # Priority 4: Fallback to first image from images/ folder
    elif image_path is None:
        exts = {".jpg", ".jpeg", ".png", ".webp"}
        images_dir = "images"
        all_files = sorted(os.listdir(images_dir))
        image_files = [
            f for f in all_files
            if os.path.splitext(f)[1].lower() in exts
        ]
        if not image_files:
            raise RuntimeError("No images available in images folder and no 'image' provided")

        image_path = os.path.join(images_dir, image_files[0])

    # Use provided cities if any, otherwise fall back to global CITIES
    cities_arg = cities if cities is not None else CITIES

    # Texts
    blessing_text = message  # if None, generate_poster/compose_poster will use defaults
    if hide_blessing:
        blessing_text = ""  # Empty string to hide blessing line

    dedication_text = None
    if hide_dedication:
        dedication_text = ""  # Empty string to hide dedication line
    elif leiluy_neshama:
        dedication_text = f'זמני השבת לע"נ {leiluy_neshama}'

    poster_bytes = generate_poster(
        image_path=image_path,
        start_date=start_date,
        cities=cities_arg,
        blessing_text=blessing_text,
        dedication_text=dedication_text,
        date_format=date_format,
    )

    return poster_bytes


class handler(BaseHTTPRequestHandler):
    """
    Vercel serverless function entrypoint using BaseHTTPRequestHandler.
    """

    def do_POST(self):
        # Read request body
        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length) if content_length > 0 else b"{}"

        try:
            payload = json.loads(raw_body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            payload = {}

        try:
            poster_bytes = build_poster_from_payload(payload)

            # Send response headers
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.end_headers()

            # Write raw PNG bytes to response
            self.wfile.write(poster_bytes)
        except Exception as e:
            # If something goes wrong, return 500 and a simple error message
            error_msg = f"Internal Server Error: {e}".encode("utf-8")
            self.send_response(500)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(error_msg)
