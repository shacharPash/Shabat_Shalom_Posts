"""
Legacy FastAPI endpoint for poster generation.

This module provides a simple FastAPI app that delegates to the shared
build_poster_from_payload function. For full functionality including
base64 and URL image support, use service.py or api/poster.py.
"""

from typing import Any, Dict

from fastapi import FastAPI, Body
from fastapi.responses import Response

from api.poster import build_poster_from_payload


app = FastAPI()


@app.post("/poster")
async def create_poster(payload: Dict[str, Any] = Body(default={})):
    """
    Create a Shabbat/Yom Tov poster.

    Payload example:
    {
      "imageBase64": "...",                 # base64-encoded image (highest priority)
      "imageUrl": "https://...",            # URL to download image from
      "image": "images/example.jpg",        # local path (lowest priority)
      "message": "לחיי שמחות קטנות וגדולות",
      "leiluyNeshama": "אורי בורנשטיין הי\"ד",
      "cities": [
        {"name": "...", "lat": ..., "lon": ..., "candle_offset": ...}
      ],
      "startDate": "YYYY-MM-DD"
    }
    """
    poster_bytes = build_poster_from_payload(payload or {})
    return Response(content=poster_bytes, media_type="image/png")

