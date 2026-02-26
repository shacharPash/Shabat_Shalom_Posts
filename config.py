"""
Configuration module for Shabbat/Yom Tov Poster Generator.

This module centralizes all configuration values and supports environment variable overrides.
All settings can be customized via environment variables - see .env.example for details.
"""

import os
from typing import Any, Dict, List

# ========= IMAGE CONFIGURATION =========

def _get_img_size() -> tuple[int, int]:
    """Get image size from environment or use default."""
    width = int(os.getenv("IMG_WIDTH", "1080"))
    height = int(os.getenv("IMG_HEIGHT", "1080"))
    return (width, height)

IMG_SIZE = _get_img_size()

# ========= TIMEZONE CONFIGURATION =========

TZID = os.getenv("TZID", "Asia/Jerusalem")

# ========= WATERMARK CONFIGURATION =========

WATERMARK_PATH = os.path.join(
    os.path.dirname(__file__), 
    "public", 
    "static", 
    os.getenv("WATERMARK_FILENAME", "watermark.png")
)
WATERMARK_SIZE = int(os.getenv("WATERMARK_SIZE", "60"))  # Width in pixels
WATERMARK_MARGIN = int(os.getenv("WATERMARK_MARGIN", "10"))  # Margin from edges in pixels
WATERMARK_OPACITY = float(os.getenv("WATERMARK_OPACITY", "0.5"))  # 0.0 = invisible, 1.0 = fully opaque

# ========= FONT CONFIGURATION =========

def _get_font_candidates(env_var: str, default: List[str]) -> List[str]:
    """Get font candidates from environment or use defaults."""
    env_value = os.getenv(env_var)
    if env_value:
        # Split by comma and strip whitespace
        return [f.strip() for f in env_value.split(",")]
    return default

_FONT_CANDIDATES_BOLD = _get_font_candidates(
    "FONT_CANDIDATES_BOLD",
    ["Alef-Bold.ttf", "Alef-Regular.ttf", "DejaVuSans.ttf"]
)

_FONT_CANDIDATES_REGULAR = _get_font_candidates(
    "FONT_CANDIDATES_REGULAR",
    ["Alef-Regular.ttf", "DejaVuSans.ttf"]
)

# ========= DEFAULT CITIES CONFIGURATION =========

# Default cities - major Israeli cities (neutral defaults)
DEFAULT_CITIES: List[Dict[str, Any]] = [
    {"name": "ירושלים", "lat": 31.779737, "lon": 35.209554, "candle_offset": 40},
    {"name": "תל אביב -יפו", "lat": 32.079112, "lon": 34.777326, "candle_offset": 20},
    {"name": "חיפה", "lat": 32.801771, "lon": 35.000609, "candle_offset": 20},
    {"name": "באר שבע", "lat": 31.256689, "lon": 34.786409, "candle_offset": 20},
]

# Keep CITIES as alias for backward compatibility
CITIES = DEFAULT_CITIES

# ========= HEBCAL API CONFIGURATION =========

def get_hebcal_base_url() -> str:
    """Get Hebcal API base URL from environment or use default."""
    return os.getenv("HEBCAL_API_URL", "https://www.hebcal.com/hebcal")

def get_hebcal_default_lat() -> float:
    """Get default latitude for Hebcal API calls."""
    return float(os.getenv("HEBCAL_DEFAULT_LAT", "31.778117828230577"))

def get_hebcal_default_lon() -> float:
    """Get default longitude for Hebcal API calls."""
    return float(os.getenv("HEBCAL_DEFAULT_LON", "35.23599222120022"))

# ========= API TIMEOUT CONFIGURATION =========

API_TIMEOUT = int(os.getenv("API_TIMEOUT", "30"))  # Timeout in seconds for API requests

