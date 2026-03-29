import json
import os
import sys
from http.server import BaseHTTPRequestHandler
from ipaddress import ip_address, ip_network
from urllib.parse import urlparse

# Add parent directory to path for Vercel serverless environment
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Import other dependencies (may fail, but handler should still load)
import base64
import socket
import tempfile
from datetime import date
from typing import Any, Dict, List, Optional

import requests


# Private/internal IP ranges to block for SSRF protection
BLOCKED_IP_NETWORKS = [
    ip_network("127.0.0.0/8"),      # Loopback
    ip_network("10.0.0.0/8"),       # Private Class A
    ip_network("172.16.0.0/12"),    # Private Class B
    ip_network("192.168.0.0/16"),   # Private Class C
    ip_network("169.254.0.0/16"),   # Link-local
    ip_network("::1/128"),          # IPv6 loopback
    ip_network("fc00::/7"),         # IPv6 private
    ip_network("fe80::/10"),        # IPv6 link-local
]


def is_safe_url(url: str) -> bool:
    """
    Check if a URL is safe to fetch (not pointing to internal/private resources).

    Returns True if the URL is safe, False if it could be an SSRF attack.
    """
    try:
        parsed = urlparse(url)

        # Only allow http and https schemes
        if parsed.scheme not in ("http", "https"):
            return False

        hostname = parsed.hostname
        if not hostname:
            return False

        # Block localhost variants
        hostname_lower = hostname.lower()
        if hostname_lower in ("localhost", "localhost.localdomain"):
            return False

        # Resolve hostname to IP addresses
        try:
            addr_info = socket.getaddrinfo(hostname, None)
            for family, _, _, _, sockaddr in addr_info:
                ip_str = sockaddr[0]
                ip = ip_address(ip_str)

                # Check if IP is in any blocked network
                for network in BLOCKED_IP_NETWORKS:
                    if ip in network:
                        return False
        except socket.gaierror:
            # DNS resolution failed - allow it (will fail at request time anyway)
            pass

        return True
    except Exception:
        # Any parsing error means unsafe URL
        return False

from make_shabbat_posts import generate_poster, DEFAULT_CITIES
from cities import get_cities_list, build_city_lookup, map_city_payload
from rate_limiter import RateLimiter

# Load cities once at module level (cached internally)
GEOJSON_CITIES = get_cities_list()
CITY_BY_NAME = build_city_lookup(GEOJSON_CITIES)

# Rate limiter: 10 requests per minute per IP
_rate_limiter = RateLimiter(max_requests=10, window_seconds=60)


def _detect_image_suffix(image_data: bytes) -> str:
    """Detect image/video format from magic bytes and return appropriate file suffix."""
    # GIF
    if image_data[:6] in (b'GIF87a', b'GIF89a'):
        return '.gif'
    # PNG
    elif image_data[:8] == b'\x89PNG\r\n\x1a\n':
        return '.png'
    # MP4 (ftyp box - appears at offset 4)
    elif len(image_data) >= 12 and b'ftyp' in image_data[:12]:
        return '.mp4'
    # WebM (EBML header)
    elif image_data[:4] == b'\x1a\x45\xdf\xa3':
        return '.webm'
    else:
        return '.jpg'


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
      ],

      # Aspect ratio control:
      "aspectRatio": "1:1"     // "1:1" (square), "4:5" (portrait), or "auto"
      "flexibleAspect": false  // DEPRECATED: use aspectRatio="auto" instead

      # Sefirat HaOmer mode:
      "omerMode": true,                    # enable Sefirat HaOmer poster mode
      "omerDate": "2025-04-20"             # optional: specific date for Omer count (for testing)
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
    if omer_day_direct is not None:
        omer_day_direct = int(omer_day_direct)
        if omer_day_direct < 1 or omer_day_direct > 49:
            raise ValueError(f"omerDay must be 1-49, got {omer_day_direct}")

    start_date_str: Optional[str] = payload.get("startDate")
    if start_date_str:
        start_date = date.fromisoformat(start_date_str)
    else:
        start_date = None

    # Priority 1: imageBase64
    if image_base64:
        try:
            image_bytes = base64.b64decode(image_base64)
            # Detect format from magic bytes
            suffix = _detect_image_suffix(image_bytes)
            # Save to a temporary file (cloud-safe: uses /tmp)
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            tmp.write(image_bytes)
            tmp.close()
            image_path = tmp.name
        except Exception as e:
            raise RuntimeError(f"Failed to decode imageBase64: {e}")

    # Priority 2: imageUrl
    elif image_url:
        # SSRF protection: validate URL before fetching
        if not is_safe_url(image_url):
            raise ValueError("Unsafe imageUrl: URL points to internal/private resource")

        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            # Optimized timeout for Vercel free tier (10s limit) with simple retry
            r = None
            last_error = None
            for attempt in range(2):
                try:
                    r = requests.get(image_url, timeout=6, headers=headers)
                    if r.status_code == 200:
                        break
                except requests.RequestException as e:
                    last_error = e
                    if attempt == 0:
                        continue  # Retry once
                    raise
            if r is None or r.status_code != 200:
                raise RuntimeError(f"Failed to download image from imageUrl after retries: {last_error or 'HTTP error'}")
            # Detect format from magic bytes
            suffix = _detect_image_suffix(r.content)
            # Save to a temporary file (cloud-safe: uses /tmp)
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            tmp.write(r.content)
            tmp.close()
            image_path = tmp.name
        except requests.RequestException as e:
            raise RuntimeError(f"Failed to download image from imageUrl: {e}")

    # Priority 3: image (local path) - already set from payload.get("image")
    # Priority 4: Fallback - use mode-specific default or first image from images/ folder
    elif image_path is None:
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        # For Omer mode, use the Omer-specific default background
        if omer_mode:
            omer_default_paths = [
                # Vercel serverless - api folder (highest priority)
                os.path.join(os.path.dirname(__file__), "omer_default.png"),
                # Local development - public folder
                os.path.join(project_root, "public", "static", "backgrounds", "omer_default.png"),
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
                os.path.join(project_root, "public", "static", "backgrounds", "shabat_default.png"),
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
        is_allowed, remaining = _rate_limiter.check(client_ip)

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
            # Read request body
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length) if content_length > 0 else b""

            # Parse JSON payload
            payload = json.loads(body.decode("utf-8")) if body else {}

            # Map city names to full city objects with coordinates
            map_city_payload(payload, CITY_BY_NAME)

            # Generate poster
            poster_bytes = build_poster_from_payload(payload)

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
            self.send_header("Cache-Control", "public, max-age=3600")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()
            self.wfile.write(poster_bytes)

        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}")  # Log full details
            error_msg = "שגיאה בפורמט הבקשה".encode("utf-8")
            self.send_response(400)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()
            self.wfile.write(error_msg)

        except ValueError as e:
            # Handle validation errors (e.g., unsafe URL for SSRF protection)
            print(f"Validation error: {e}")  # Log full details
            error_msg = "שגיאה בנתוני הבקשה".encode("utf-8")
            self.send_response(400)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()
            self.wfile.write(error_msg)

        except Exception as e:
            print(f"Internal error in poster generation: {e}")  # Log full details
            error_msg = "שגיאה ביצירת הפוסטר".encode("utf-8")
            self.send_response(500)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()
            self.wfile.write(error_msg)

    def do_OPTIONS(self):
        """Handle CORS preflight requests."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

