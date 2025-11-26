from typing import Any, Dict
from fastapi import FastAPI, Body
from fastapi.responses import Response

from api.poster import build_poster_from_payload


app = FastAPI()


@app.post("/poster")
async def create_poster(payload: Dict[str, Any] = Body(default={})):
    """
    FastAPI endpoint that:
    - Receives JSON payload
    - Uses build_poster_from_payload to generate a PNG
    - Returns image/png as response
    """
    if payload is None:
        payload = {}

    poster_bytes = build_poster_from_payload(payload)
    return Response(content=poster_bytes, media_type="image/png")
