"""Shared public input limits and media inspection without remote fetching."""
import base64
import binascii
import io
import math
import re
import struct
from datetime import date

from PIL import Image, UnidentifiedImageError

MAX_REQUEST_BODY_BYTES = 4_400_000
MAX_RESPONSE_BYTES = 4_400_000
MAX_IMAGE_BYTES = 3 * 1024 * 1024
MAX_SOURCE_PIXELS = 20_000_000
MAX_SOURCE_DIMENSION = 12_000
MAX_GIF_FRAMES = 30
MAX_GIF_PIXELS = 40_000_000


class InputError(ValueError):
    status_code = 400

    def __init__(self, message="שגיאה בנתוני הבקשה"):
        super().__init__(message)


class MediaTooLarge(InputError):
    status_code = 413

    def __init__(self):
        super().__init__("התמונה או הבקשה גדולות מדי")


class UnsupportedMedia(InputError):
    status_code = 415

    def __init__(self):
        super().__init__("סוג הקובץ אינו נתמך. יש להעלות תמונת JPEG, PNG, WebP או GIF מוגבל. העלאת וידאו אינה נתמכת")


def validate_content_length(value):
    if value is None:
        return None
    if not re.fullmatch(r"[0-9]+", str(value)):
        raise InputError()
    try:
        length = int(value)
    except ValueError:
        raise InputError() from None
    if length > MAX_REQUEST_BODY_BYTES:
        raise MediaTooLarge()
    return length


def validate_response_size(data):
    if len(data) > MAX_RESPONSE_BYTES:
        raise MediaTooLarge()


def _number(value, minimum, maximum, *, integer=False):
    if type(value) not in (int, float) or (integer and type(value) is not int):
        raise InputError()
    if not minimum <= value <= maximum or not math.isfinite(value):
        raise InputError()


def _text(value, limit, *, nullable=True):
    if value is None and nullable:
        return
    if not isinstance(value, str) or len(value) > limit:
        raise InputError()


def validate_payload(payload, *, allow_local_image=False):
    if not isinstance(payload, dict):
        raise InputError()
    # Reject forbidden sources even when another source would take priority.
    if payload.get("imageUrl") is not None:
        raise InputError("טעינת תמונה מקישור אינה נתמכת. יש להעלות קובץ תמונה")
    if payload.get("image") is not None and not allow_local_image:
        raise InputError("יש להעלות קובץ תמונה")
    for name in ("message", "leiluyNeshama", "overrideMainTitle", "overrideSubtitle"):
        _text(payload.get(name), 500)
    for name in ("hideDedication", "hideBlessing", "showWatermark", "flexibleAspect", "omerMode"):
        if name in payload and type(payload[name]) is not bool:
            raise InputError()
    for name, choices in {
        "aspectRatio": ("1:1", "4:5", "auto"),
        "dateFormat": ("gregorian", "hebrew", "both"),
        "nusach": ("sefard", "ashkenaz", "edot_hamizrach"),
    }.items():
        if name in payload and payload[name] not in choices:
            raise InputError()
    for name in ("cropX", "cropY"):
        if payload.get(name) is not None:
            _number(payload[name], 0, 1)
    if payload.get("omerDay") is not None:
        _number(payload["omerDay"], 1, 49, integer=True)
    for name in ("startDate", "omerDate"):
        if payload.get(name) is not None:
            value = payload[name]
            if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                raise InputError()
            try:
                date.fromisoformat(value)
            except ValueError:
                raise InputError() from None
    for name in ("imageBase64", "image"):
        if payload.get(name) is not None and not isinstance(payload[name], str):
            raise InputError()
    cities, custom = payload.get("cities"), payload.get("customCities")
    for group in (cities, custom):
        if group is not None and not isinstance(group, list):
            raise InputError()
    if len(cities or []) + len(custom or []) > 12:
        raise InputError()
    for city in cities or []:
        if isinstance(city, str):
            _text(city, 100, nullable=False)
            continue
        if not isinstance(city, dict):
            raise InputError()
        _text(city.get("name"), 100, nullable=False)
        for field, low, high in (("lat", -90, 90), ("lon", -180, 180), ("candle_offset", 0, 60)):
            if field in city:
                _number(city[field], low, high, integer=field == "candle_offset")
        if ("lat" in city) != ("lon" in city):
            raise InputError()
    for city in custom or []:
        if not isinstance(city, dict):
            raise InputError()
        _text(city.get("name"), 100, nullable=False)
        for field in ("candle", "havdalah"):
            value = city.get(field)
            if not isinstance(value, str) or not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value):
                raise InputError()


def validate_geometry(width, height):
    if width <= 0 or height <= 0:
        raise InputError()
    if max(width, height) > MAX_SOURCE_DIMENSION or width * height > MAX_SOURCE_PIXELS:
        raise MediaTooLarge()


def _inspect_gif(data):
    """Count GIF image descriptors without decoding any image frames."""
    if len(data) < 13:
        raise InputError()
    width, height = struct.unpack_from("<HH", data, 6)
    validate_geometry(width, height)
    packed = data[10]
    position = 13 + (3 * (2 ** ((packed & 7) + 1)) if packed & 128 else 0)
    frames = 0

    def skip_blocks(position):
        while position < len(data):
            length = data[position]
            position += 1
            if length == 0:
                return position
            position += length
        raise InputError()

    while position < len(data):
        marker = data[position]
        position += 1
        if marker == 0x3B:
            if not frames:
                raise InputError()
            return
        if marker == 0x21:
            position = skip_blocks(position + 1)
        elif marker == 0x2C:
            if position + 9 > len(data):
                raise InputError()
            left, top, frame_width, frame_height, packed = struct.unpack_from("<HHHHB", data, position)
            validate_geometry(frame_width, frame_height)
            if left + frame_width > width or top + frame_height > height:
                raise InputError()
            frames += 1
            if frames > MAX_GIF_FRAMES or frames * width * height > MAX_GIF_PIXELS:
                raise MediaTooLarge()
            position += 9 + (3 * (2 ** ((packed & 7) + 1)) if packed & 128 else 0)
            position = skip_blocks(position + 1)  # LZW minimum code size
        else:
            raise InputError()
    raise InputError()


def inspect_image(data):
    if len(data) > MAX_IMAGE_BYTES:
        raise MediaTooLarge()
    if data[:6] in (b"GIF87a", b"GIF89a"):
        _inspect_gif(data)
    try:
        # Restrict plugins as well as accepted output formats.
        with Image.open(io.BytesIO(data), formats=("JPEG", "PNG", "WEBP", "GIF")) as image:
            validate_geometry(*image.size)
            fmt = image.format
            if fmt != "GIF" and getattr(image, "is_animated", False):
                raise UnsupportedMedia()
            image.verify()
        # verify() alone does not decode JPEG entropy data. Decode bounded
        # pixels here so corrupt uploads are input errors before rendering.
        with Image.open(io.BytesIO(data), formats=("JPEG", "PNG", "WEBP", "GIF")) as image:
            while True:
                image.load()
                try:
                    image.seek(image.tell() + 1)
                except EOFError:
                    break
        return {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp", "GIF": ".gif"}[fmt]
    except InputError:
        raise
    except Image.DecompressionBombError:
        raise MediaTooLarge() from None
    except UnidentifiedImageError:
        raise UnsupportedMedia() from None
    except (OSError, ValueError, SyntaxError, EOFError, struct.error):
        raise InputError("קובץ התמונה אינו תקין") from None


def decode_upload(value):
    if len(value) > 4 * ((MAX_IMAGE_BYTES + 2) // 3):
        raise MediaTooLarge()
    try:
        data = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError):
        raise InputError("קידוד התמונה אינו תקין") from None
    return data, inspect_image(data)
