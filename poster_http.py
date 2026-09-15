"""Thin HTTP adapters sharing the public poster boundary and local routes."""
import json

from fastapi import Request
from fastapi.responses import Response, JSONResponse, FileResponse

from media_validation import InputError, MediaTooLarge, MAX_REQUEST_BODY_BYTES, validate_content_length, validate_response_size

PRIVATE_HEADERS = {"Cache-Control": "private, no-store"}


async def create_poster_response(request: Request, builder):
    try:
        validate_content_length(request.headers.get("content-length"))
        body = bytearray()
        async for chunk in request.stream():
            if len(body) + len(chunk) > MAX_REQUEST_BODY_BYTES:
                raise MediaTooLarge()
            body.extend(chunk)
        payload = json.loads(body) if body else {}
        poster_bytes = builder(payload)
        validate_response_size(poster_bytes)
        media_type = "image/gif" if poster_bytes[:6] in (b"GIF87a", b"GIF89a") else "image/png"
        return Response(poster_bytes, media_type=media_type, headers=PRIVATE_HEADERS)
    except InputError as error:
        return Response(str(error), status_code=error.status_code, headers=PRIVATE_HEADERS)
    except (ValueError, UnicodeError):
        return Response("שגיאה בנתוני הבקשה", status_code=400, headers=PRIVATE_HEADERS)
    except Exception:
        return Response("שגיאה ביצירת הפוסטר", status_code=500, headers=PRIVATE_HEADERS)


def register_public_routes(app):
    from api.omer_info import get_omer_info
    from api.static import resolve_static_path
    from api.upcoming_events import get_upcoming_events

    @app.get("/omer-info")
    async def omer_info(request: Request):
        try:
            return JSONResponse(get_omer_info(request.query_params), headers={"Cache-Control": "public, max-age=300"})
        except ValueError:
            return JSONResponse({"error": "פורמט תאריך לא תקין"}, status_code=400)
        except Exception:
            return JSONResponse({"error": "שגיאה בקבלת מידע העומר"}, status_code=500)

    @app.get("/upcoming-events")
    async def upcoming_events():
        return get_upcoming_events()

    @app.get("/{asset_path:path}")
    async def public_asset(asset_path: str):
        try:
            path = resolve_static_path("/" + asset_path)
        except ValueError:
            return Response(status_code=403)
        if not path.is_file():
            return Response(status_code=404)
        return FileResponse(path)
