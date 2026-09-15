"""Regression tests for the public media boundary, using small isolated fixtures."""
import base64
import io
import struct
from pathlib import Path

import pytest
from PIL import Image

from api import poster
from image_utils import _fit_background_fixed


def upload(size=(16, 16), fmt="PNG"):
    stream = io.BytesIO()
    Image.new("RGB", size, "blue").save(stream, fmt)
    return base64.b64encode(stream.getvalue()).decode()


@pytest.mark.parametrize("url", ["https://example.com/a.png", "http://127.0.0.1/secret", "file:///tmp/private"])
def test_remote_input_rejected_before_dns_or_http(monkeypatch, url):
    def forbidden(*args, **kwargs):
        pytest.fail("Remote input reached the network")
    monkeypatch.setattr("socket.getaddrinfo", forbidden)
    monkeypatch.setattr("requests.get", forbidden)
    with pytest.raises(ValueError):
        poster.build_poster_from_payload({"imageUrl": url})


def test_public_builder_rejects_local_path(tmp_path):
    path = tmp_path / "private.png"
    Image.new("RGB", (4, 4)).save(path)
    with pytest.raises(ValueError):
        poster.build_poster_from_payload({"image": str(path), "omerMode": True, "omerDay": 1})


def test_trusted_local_path_preserves_file(tmp_path):
    path = tmp_path / "private.png"
    Image.new("RGB", (4, 4)).save(path)
    result = poster.build_poster_from_payload({"image": str(path), "omerMode": True, "omerDay": 1}, allow_local_image=True)
    assert result.startswith(b"\x89PNG")
    assert path.exists()


@pytest.mark.parametrize("fail", [False, True])
def test_uploaded_file_removed_after_render(monkeypatch, tmp_path, fail):
    monkeypatch.setattr(poster.tempfile, "tempdir", str(tmp_path))
    def render(**kwargs):
        assert Path(kwargs["image_path"]).exists()
        if fail:
            raise RuntimeError("render failed")
        return b"poster"
    monkeypatch.setattr(poster, "generate_poster", render)
    if fail:
        with pytest.raises(RuntimeError, match="render failed"):
            poster.build_poster_from_payload({"imageBase64": upload()})
    else:
        assert poster.build_poster_from_payload({"imageBase64": upload()}) == b"poster"
    assert list(tmp_path.iterdir()) == []


def test_psd_masquerading_as_jpeg_is_rejected():
    psd = b"8BPS" + struct.pack(">H6sHIIHH", 1, b"\0" * 6, 3, 1, 1, 8, 3) + struct.pack(">IIIH", 0, 0, 0, 0) + bytes([255, 0, 0])
    with pytest.raises(ValueError) as exc:
        poster.build_poster_from_payload({"imageBase64": base64.b64encode(psd).decode(), "omerMode": True, "omerDay": 1})
    assert exc.value.status_code == 415


@pytest.mark.parametrize("size", [(1, 12001), (12001, 1), (4500, 4500)])
def test_source_geometry_rejected_before_render(monkeypatch, size):
    # Headers only: no giant decoded image is allocated for the regression.
    import zlib
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", *size, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(b"")) + chunk(b"IEND", b"")
    def forbidden(**kwargs):
        pytest.fail("Over-limit media reached the renderer")
    monkeypatch.setattr(poster, "generate_poster", forbidden)
    with pytest.raises(ValueError) as exc:
        poster.build_poster_from_payload({"imageBase64": base64.b64encode(png).decode()})
    assert exc.value.status_code == 413


def test_narrow_image_crops_before_bounded_resize(monkeypatch):
    source = Image.new("RGB", (1, 12000), "blue")
    original_resize = Image.Image.resize
    def bounded_resize(self, size, *args, **kwargs):
        assert max(size) <= 1080, "unbounded intermediate resize"
        return original_resize(self, size, *args, **kwargs)
    monkeypatch.setattr(Image.Image, "resize", bounded_resize)
    assert _fit_background_fixed(source, (1080, 1080)).size == (1080, 1080)


@pytest.mark.parametrize("position,color", [((0, 0), (255, 0, 0)), ((1, 1), (0, 0, 255))])
def test_crop_position_preserves_selected_region(position, color):
    source = Image.new("RGB", (40, 20), "red")
    source.paste("blue", (20, 0, 40, 20))
    result = _fit_background_fixed(source, (20, 20), position)
    assert result.getpixel((10, 10)) == color


@pytest.mark.parametrize("payload", [
    [], None, {"hideBlessing": "false"}, {"showWatermark": 1},
    {"cropX": float("nan"), "cropY": .5}, {"cropX": -1}, {"cropY": 1.1},
    {"cropX": "0.5"}, {"omerDay": True}, {"omerDay": 1.5},
    {"aspectRatio": "99:1"}, {"dateFormat": "unknown"}, {"nusach": "unknown"},
    {"startDate": "2025-02-30"}, {"omerDate": 15}, {"message": "x" * 501},
    {"overrideSubtitle": []}, {"cities": {}}, {"cities": [12]},
    {"cities": ["x" * 101]}, {"cities": ["ירושלים"] * 7, "customCities": [{"name": "א", "candle": "16:30", "havdalah": "17:45"}] * 6},
    {"cities": [{"name": "א", "lat": float("inf"), "lon": 2}]},
    {"cities": [{"name": "א", "lat": 91, "lon": 2}]},
    {"customCities": [{"name": "א", "candle": "25:99", "havdalah": "17:45"}]},
    {"imageBase64": 123},
])
def test_invalid_payload_rejected_before_render(monkeypatch, payload):
    def forbidden(**kwargs):
        pytest.fail("Invalid payload reached the renderer")
    monkeypatch.setattr(poster, "generate_poster", forbidden)
    with pytest.raises(ValueError):
        poster.build_poster_from_payload(payload)


@pytest.mark.parametrize("fmt", ["JPEG", "PNG", "WEBP", "GIF"])
def test_supported_uploads_render(fmt):
    result = poster.build_poster_from_payload({"imageBase64": upload(fmt=fmt), "omerMode": True, "omerDay": 1})
    assert result.startswith(b"\x89PNG")


def test_video_upload_has_unsupported_status():
    with pytest.raises(ValueError) as exc:
        poster.build_poster_from_payload({"imageBase64": base64.b64encode(b"\0\0\0\x18ftypmp42" + b"\0" * 30).decode()})
    assert exc.value.status_code == 415


def test_oversized_decoded_upload():
    with pytest.raises(ValueError) as exc:
        poster.build_poster_from_payload({"imageBase64": base64.b64encode(b"x" * (3 * 1024 * 1024 + 1)).decode()})
    assert exc.value.status_code == 413


def test_gif_frame_limit_before_render(monkeypatch):
    frames = [Image.new("RGB", (2, 2), (i, 0, 0)) for i in range(31)]
    stream = io.BytesIO()
    frames[0].save(stream, "GIF", save_all=True, append_images=frames[1:], optimize=False)
    def forbidden(**kwargs):
        pytest.fail("Over-limit GIF reached the renderer")
    monkeypatch.setattr(poster, "generate_poster", forbidden)
    with pytest.raises(ValueError) as exc:
        poster.build_poster_from_payload({"imageBase64": base64.b64encode(stream.getvalue()).decode()})
    assert exc.value.status_code == 413


def test_corrupt_jpeg_is_input_error_before_render(monkeypatch):
    stream = io.BytesIO()
    Image.new("RGB", (16, 16), "blue").save(stream, "JPEG")
    truncated = stream.getvalue()[:-10]
    def forbidden(**kwargs):
        pytest.fail("Corrupt JPEG reached renderer")
    monkeypatch.setattr(poster, "generate_poster", forbidden)
    with pytest.raises(ValueError) as exc:
        poster.build_poster_from_payload({"imageBase64": base64.b64encode(truncated).decode()})
    assert exc.value.status_code == 400


def test_gif_aggregate_pixels_checked_without_decoding(monkeypatch):
    # Three logical 4000x4000 canvases exceed 40 million aggregate pixels.
    # Only tiny GIF headers/descriptors are constructed, no canvases allocated.
    data = b"GIF89a" + struct.pack("<HHBBB", 4000, 4000, 0, 0, 0)
    descriptor = b"," + struct.pack("<HHHHB", 0, 0, 4000, 4000, 0) + b"\x02\x00"
    data += descriptor * 3 + b";"
    def forbidden(*args, **kwargs):
        pytest.fail("Over-limit GIF reached Pillow decoding")
    monkeypatch.setattr(Image, "open", forbidden)
    with pytest.raises(ValueError) as exc:
        poster.build_poster_from_payload({"imageBase64": base64.b64encode(data).decode()})
    assert exc.value.status_code == 413


def test_animated_gif_remains_supported():
    frames = [Image.new("RGB", (16, 16), color) for color in ("red", "blue")]
    stream = io.BytesIO()
    frames[0].save(stream, "GIF", save_all=True, append_images=frames[1:], duration=[100, 200])
    result = poster.build_poster_from_payload({"imageBase64": base64.b64encode(stream.getvalue()).decode(), "startDate": "2025-01-24"})
    with Image.open(io.BytesIO(result)) as image:
        assert image.format == "GIF"
        assert image.n_frames == 2
        assert image.size == (1080, 1080)


def test_uploaded_file_removed_if_write_fails(monkeypatch, tmp_path):
    real_temporary_file = poster.tempfile.NamedTemporaryFile
    class FailedWrite:
        def __init__(self, **kwargs):
            self.file = real_temporary_file(dir=tmp_path, **kwargs)
            self.name = self.file.name
        def __enter__(self):
            return self
        def __exit__(self, *args):
            self.file.close()
        def write(self, data):
            raise OSError("disk full")
    monkeypatch.setattr(poster.tempfile, "NamedTemporaryFile", FailedWrite)
    with pytest.raises(OSError):
        poster.build_poster_from_payload({"imageBase64": upload()})
    assert list(tmp_path.iterdir()) == []


def test_decoded_upload_at_limit_is_accepted():
    raw = base64.b64decode(upload())
    raw += b"\0" * (3 * 1024 * 1024 - len(raw))
    result = poster.build_poster_from_payload({"imageBase64": base64.b64encode(raw).decode(), "omerMode": True, "omerDay": 1})
    assert result.startswith(b"\x89PNG")


@pytest.mark.parametrize("supplied_offset,effective_offset", [(None, 20), (40, 40)])
def test_coordinate_city_defaults_without_mutating_caller(monkeypatch, supplied_offset, effective_offset):
    import copy
    city = {"name": "ירושלים", "lat": 32.1, "lon": 34.8}
    if supplied_offset is not None:
        city["candle_offset"] = supplied_offset
    payload = {"startDate": "2025-01-24", "cities": [city]}
    original = copy.deepcopy(payload)
    actual_cities = []
    real_render = poster.generate_poster

    def observe_render(**kwargs):
        actual_cities.extend(copy.deepcopy(kwargs["cities"]))
        return real_render(**kwargs)

    monkeypatch.setattr(poster, "generate_poster", observe_render)
    result = poster.build_poster_from_payload(payload)
    assert result.startswith(b"\x89PNG")
    assert actual_cities == [{"name": "ירושלים", "lat": 32.1, "lon": 34.8, "candle_offset": effective_offset}]
    assert payload == original
