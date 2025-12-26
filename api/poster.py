import json
import os
import sys
from http.server import BaseHTTPRequestHandler

# Add parent directory to path for Vercel serverless environment
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Import other dependencies (may fail, but handler should still load)
import base64
import tempfile
from datetime import date
from typing import Any, Dict, List, Optional

import requests

from make_shabbat_posts import generate_poster, DEFAULT_CITIES


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
      "dateFormat": "gregorian",           # "gregorian", "hebrew", or "both"

      # Manual overrides (optional - override auto-detected values):
      "overrideMainTitle": "שבת שלום",     # custom main title (greeting)
      "overrideSubtitle": "פרשת... | ...", # custom subtitle (parsha + date line)

      # Custom cities with manual times:
      "customCities": [
        { "name": "עיר מותאמת", "candle": "16:30", "havdalah": "17:45" }
      ]
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

    # Manual overrides
    override_main_title: Optional[str] = payload.get("overrideMainTitle")
    override_subtitle: Optional[str] = payload.get("overrideSubtitle")

    # Custom cities with manual times
    custom_cities: Optional[List[Dict[str, str]]] = payload.get("customCities")

    # Watermark control (enabled by default)
    show_watermark: bool = payload.get("showWatermark", True)

    # Image crop position (x, y) as percentages 0.0-1.0
    crop_x: Optional[float] = payload.get("cropX")
    crop_y: Optional[float] = payload.get("cropY")
    crop_position = None
    if crop_x is not None and crop_y is not None:
        crop_position = (float(crop_x), float(crop_y))

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

    # Use provided cities if any, otherwise use default cities (major Israeli cities)
    cities_arg = cities if cities is not None else DEFAULT_CITIES

    # Texts - no defaults, only use what user provided
    # Empty string means hide, None also means hide (no defaults)
    blessing_text = ""
    if message and not hide_blessing:
        blessing_text = message

    dedication_text = ""
    if leiluy_neshama and not hide_dedication:
        dedication_text = f'זמני השבת לע"נ {leiluy_neshama}'

    # Build overrides dict (only include non-None values)
    overrides = {}
    if override_main_title:
        overrides["main_title"] = override_main_title
    if override_subtitle:
        overrides["subtitle"] = override_subtitle
    if custom_cities:
        overrides["custom_cities"] = custom_cities

    poster_bytes = generate_poster(
        image_path=image_path,
        start_date=start_date,
        cities=cities_arg,
        blessing_text=blessing_text,
        dedication_text=dedication_text,
        date_format=date_format,
        overrides=overrides if overrides else None,
        crop_position=crop_position,
        show_watermark=show_watermark,
    )

    return poster_bytes


# Vercel serverless function handler
class handler(BaseHTTPRequestHandler):
    """Vercel serverless function entrypoint for poster generation."""

    def do_POST(self):
        """Handle POST request to generate a poster."""
        try:
            # Read request body
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length) if content_length > 0 else b""

            # Parse JSON payload
            payload = json.loads(body.decode("utf-8")) if body else {}

            # Generate poster
            poster_bytes = build_poster_from_payload(payload)

            # Send successful response
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(poster_bytes)))
            self.end_headers()
            self.wfile.write(poster_bytes)

        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON: {e}".encode("utf-8")
            self.send_response(400)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(error_msg)

        except Exception as e:
            error_msg = f"Internal Server Error: {e}".encode("utf-8")
            self.send_response(500)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(error_msg)

    def do_OPTIONS(self):
        """Handle CORS preflight requests."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

