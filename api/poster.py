import json
import os
import sys
from http.server import BaseHTTPRequestHandler
import tempfile
from datetime import date
from typing import Any, Dict, List, Optional

# Add parent directory to path for Vercel serverless environment.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from media_validation import (
    InputError, MediaTooLarge, UnsupportedMedia, MAX_REQUEST_BODY_BYTES,
    MAX_IMAGE_BYTES, decode_upload, inspect_image, validate_payload,
    validate_content_length, validate_response_size,
)

from make_shabbat_posts import generate_poster, DEFAULT_CITIES
from cities import get_cities_list, build_city_lookup, map_city_payload
from rate_limiter import RateLimiter, RateLimitUnavailable

# Load cities once at module level (cached internally)
GEOJSON_CITIES = get_cities_list()
CITY_BY_NAME = build_city_lookup(GEOJSON_CITIES)

# Rate limiter: 10 requests per minute per IP
_rate_limiter = RateLimiter(max_requests=10, window_seconds=60)


def _detect_image_suffix(image_data: bytes) -> str:
    """Inspect the actual format, accepting only supported bounded media."""
    return inspect_image(image_data)


def build_poster_from_payload(payload: Dict[str, Any], *, allow_local_image=False) -> bytes:
    """Render a poster from validated input. Local files require explicit trust.

    Public callers upload base64 images or use the bundled default background.
    Returns PNG or bounded GIF bytes and raises InputError for public input errors.
    """
    validate_payload(payload, allow_local_image=allow_local_image)
    payload = payload.copy()
    # Keep explicit coordinate objects for trusted bot/CLI callers and map UI names.
    if payload.get("cities"):
        if all(
            isinstance(city, dict) and "lat" in city and "lon" in city
            for city in payload["cities"]
        ):
            payload["cities"] = [
                {"candle_offset": 20, **city} for city in payload["cities"]
            ]
        else:
            map_city_payload(payload, CITY_BY_NAME)
    temporary_path = None
    try:
        if payload.get("imageBase64") is not None:
            image_bytes, suffix = decode_upload(payload["imageBase64"])
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as uploaded:
                temporary_path = uploaded.name
                uploaded.write(image_bytes)
            payload["image"] = temporary_path
        elif payload.get("image") is not None:
            with open(payload["image"], "rb") as source:
                inspect_image(source.read(MAX_IMAGE_BYTES + 1))
        return _render_payload(payload)
    finally:
        if temporary_path is not None:
            os.unlink(temporary_path)


def _render_payload(payload):
    image_path: Optional[str] = payload.get("image")
    message: Optional[str] = payload.get("message")
    leiluy_neshama: Optional[str] = payload.get("leiluyNeshama")
    hide_dedication: bool = payload.get("hideDedication", False)
    hide_blessing: bool = payload.get("hideBlessing", False)
    cities: Optional[List[Dict[str, Any]]] = payload.get("cities")
    date_format: str = payload.get("dateFormat", "both")  # "gregorian", "hebrew", or "both" - default: both (Hebrew + Gregorian)

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

    # Aspect ratio control
    aspect_ratio: str = payload.get("aspectRatio", "1:1")  # "1:1", "4:5", or "auto"

    # Flexible aspect ratio (DEPRECATED - for backward compatibility)
    flexible_aspect: bool = payload.get("flexibleAspect", False)

    # Sefirat HaOmer mode
    omer_mode: bool = payload.get("omerMode", False)
    omer_date_str: Optional[str] = payload.get("omerDate")
    omer_date: Optional[date] = None
    if omer_date_str:
        omer_date = date.fromisoformat(omer_date_str)

    # Direct omer day specification (overrides date-based calculation)
    omer_day_direct: Optional[int] = payload.get("omerDay")

    # Nusach (liturgical tradition) for Omer counting
    nusach: str = payload.get("nusach", "sefard")

    start_date_str: Optional[str] = payload.get("startDate")
    if start_date_str:
        start_date = date.fromisoformat(start_date_str)
    else:
        start_date = None

    if image_path is None:
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        # For Omer mode, use the Omer-specific default background
        if omer_mode:
            omer_default_paths = [
                # Vercel serverless - api folder (highest priority)
                os.path.join(os.path.dirname(__file__), "omer_default.png"),
                # Local development - public folder
                os.path.join(project_root, "public", "backgrounds", "omer_default.png"),
            ]
            for path in omer_default_paths:
                if os.path.isfile(path):
                    image_path = path
                    break

        # If no Omer default found (or not in Omer mode), try Shabbat default
        if image_path is None:
            shabat_default_paths = [
                # Vercel serverless - api folder (highest priority)
                os.path.join(os.path.dirname(__file__), "shabat_default.png"),
                # Local development - public folder
                os.path.join(project_root, "public", "backgrounds", "shabat_default.png"),
            ]
            for path in shabat_default_paths:
                if os.path.isfile(path):
                    image_path = path
                    break

        # If no Shabbat default found, use generic fallback from images folder
        if image_path is None:
            exts = {".jpg", ".jpeg", ".png", ".webp"}
            images_dir = os.path.join(project_root, "images")
            all_files = sorted(os.listdir(images_dir))
            image_files = [
                f for f in all_files
                if os.path.splitext(f)[1].lower() in exts
            ]
            if not image_files:
                raise RuntimeError("No images available in images folder and no 'image' provided")
            image_path = os.path.join(images_dir, image_files[0])

    # Use provided cities if any, otherwise use default cities (major Israeli cities)
    # Exception: if custom_cities are provided, allow empty cities list (don't fall back to defaults)
    if cities is not None:
        cities_arg = cities
    elif custom_cities:
        # User has custom cities only - use empty list for predefined cities
        cities_arg = []
    else:
        cities_arg = DEFAULT_CITIES

    # Texts - no defaults, only use what user provided
    # Empty string means hide, None also means hide (no defaults)
    blessing_text = ""
    if message and not hide_blessing:
        blessing_text = message

    dedication_text = ""
    if leiluy_neshama and not hide_dedication:
        dedication_text = f'לעילוי נשמת {leiluy_neshama}'

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
        aspect_ratio=aspect_ratio,
        flexible_aspect=flexible_aspect,
        omer_mode=omer_mode,
        omer_date=omer_date,
        omer_day=omer_day_direct,
        nusach=nusach,
    )

    return poster_bytes


# Vercel serverless function handler
class handler(BaseHTTPRequestHandler):
    """Vercel serverless function entrypoint for poster generation."""

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
        """Handle POST request to generate a poster."""
        # Rate limiting check
        client_ip = self._get_client_ip()
        try:
            is_allowed, remaining = _rate_limiter.check(client_ip)
        except RateLimitUnavailable:
            self._send_error(503, "Service unavailable. Try again later.")
            return

        if not is_allowed:
            error_body = b'{"error": "Rate limit exceeded. Try again later."}'
            self.send_response(429)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Retry-After", "60")
            self.end_headers()
            self.wfile.write(error_body)
            return

        try:
            content_length = validate_content_length(self.headers.get("Content-Length"))
            if self.headers.get("Transfer-Encoding"):
                raise InputError()
            body = self.rfile.read(content_length) if content_length else b""
            if content_length is not None and len(body) != content_length:
                raise InputError()
            payload = json.loads(body.decode("utf-8")) if body else {}

            # Generate poster
            poster_bytes = build_poster_from_payload(payload)
            validate_response_size(poster_bytes)

            # Detect output format from magic bytes
            # GIF starts with "GIF87a" or "GIF89a", PNG starts with \x89PNG
            if poster_bytes[:6] in (b'GIF87a', b'GIF89a'):
                content_type = "image/gif"
            else:
                content_type = "image/png"

            # Send successful response
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(poster_bytes)))
            self.send_header("Cache-Control", "private, no-store")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()
            self.wfile.write(poster_bytes)

        except InputError as error:
            self._send_error(error.status_code, str(error))
        except (ValueError, UnicodeError):
            self._send_error(400, "שגיאה בנתוני הבקשה")
        except Exception:
            self._send_error(500, "שגיאה ביצירת הפוסטר")

    def _send_error(self, status, message):
        body = message.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "private, no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        """Handle CORS preflight requests."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

