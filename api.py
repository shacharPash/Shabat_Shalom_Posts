from typing import Optional, List, Dict, Any
from datetime import date

from fastapi import FastAPI, Body
from fastapi.responses import Response

from make_shabbat_posts import generate_poster, CITIES  # import from my existing script


app = FastAPI()


@app.post("/poster")
async def create_poster(
    payload: Dict[str, Any] = Body(default={})
):
    """
    Create a Shabbat/Yom Tov poster.

    Payload example:
    {
      "image": "images/example.jpg",
      "message": "לחיי שמחות קטנות וגדולות",
      "leiluyNeshama": "אורי בורנשטיין הי\"ד",
      "cities": [
        {"name": "...", "lat": ..., "lon": ..., "candle_offset": ...}
      ],
      "startDate": "YYYY-MM-DD"
    }
    """

    image_path: Optional[str] = payload.get("image")

    message: Optional[str] = payload.get("message")
    leiluy_neshama: Optional[str] = payload.get("leiluyNeshama")
    cities: Optional[List[Dict[str, Any]]] = payload.get("cities")

    start_date_str: Optional[str] = payload.get("startDate")
    if start_date_str:
        start_date = date.fromisoformat(start_date_str)
    else:
        start_date = None

    # Pick default image if none provided
    if image_path is None:
        import os
        exts = {".jpg", ".jpeg", ".png", ".webp"}
        images_dir = "images"
        all_files = sorted(os.listdir(images_dir))
        image_files = [f for f in all_files if os.path.splitext(f)[1].lower() in exts]
        if not image_files:
            return {"error": "No images available"}
        image_path = os.path.join(images_dir, image_files[0])

    # Default cities
    cities_arg = cities if cities is not None else CITIES

    # Build blessing text and dedication
    blessing_text = message
    dedication_text = None
    if leiluy_neshama:
        dedication_text = f'זמני השבת לע"נ {leiluy_neshama}'

    poster_bytes = generate_poster(
        image_path=image_path,
        start_date=start_date,
        cities=cities_arg,
        blessing_text=blessing_text,
        dedication_text=dedication_text,
    )

    return Response(content=poster_bytes, media_type="image/png")

