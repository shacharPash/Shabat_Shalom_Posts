"""Public contracts must agree across all HTTP entry points."""
import io
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api import poster
import api.index
import service


@pytest.fixture(params=[service.app, api.index.app])
def client(request):
    with TestClient(request.param, raise_server_exceptions=False) as client:
        yield client


def test_local_file_rejected_without_echo(client, tmp_path):
    path = tmp_path / "secret-image.png"
    from PIL import Image
    Image.new("RGB", (4, 4)).save(path)
    result = client.post("/poster", json={"image": str(path), "omerMode": True, "omerDay": 1})
    assert result.status_code == 400
    assert str(path) not in result.text


@pytest.mark.parametrize("body,status", [(b"[]", 400), (b"null", 400), (b"{", 400), (b'{"hideBlessing":"false"}', 400), (b'{"imageUrl":"https://example.com/secret"}', 400), (b'{"imageBase64":"eA=="}', 415)])
def test_input_status_consistency(client, body, status):
    result = client.post("/poster", content=body)
    assert result.status_code == status
    assert "secret" not in result.text


def test_request_body_limit_before_json(client):
    result = client.post("/poster", content=b" " * (4_400_001))
    assert result.status_code == 413


def test_body_below_limit_reaches_json_parser(client):
    result = client.post("/poster", content=b" " * (4_300_000))
    assert result.status_code == 400


def test_posters_are_private(client):
    result = client.post("/poster", json={"omerMode": True, "omerDay": 1})
    assert result.status_code == 200
    assert result.headers["cache-control"] == "private, no-store"


@pytest.mark.parametrize("path", ["/backgrounds/shabat_default.png", "/backgrounds/omer_default.png", "/watermark.png", "/favicon.ico", "/apple-touch-icon.png", "/favicon-32x32.png"])
def test_public_assets_available(client, path):
    result = client.get(path)
    assert result.status_code == 200
    assert result.content == (Path(__file__).resolve().parents[1] / "public" / path.lstrip("/")).read_bytes()


def test_omer_info_local_route(client):
    result = client.get("/omer-info?date=2026-04-15")
    assert result.status_code == 200
    assert result.json()["isOmerPeriod"] is True
    assert result.json()["dayNumber"] >= 1


@pytest.mark.parametrize("path", ["/static//etc/passwd", "/static/%2fetc/passwd", "/static/%2e%2e/requirements.txt", "/static/%252e%252e/requirements.txt"])
def test_static_handler_rejects_escape(path):
    from api.static import handler
    instance = object.__new__(handler)
    instance.path = path
    instance.wfile = io.BytesIO()
    statuses = []
    instance.send_error = lambda status, *args: statuses.append(status)
    instance.send_response = lambda status: statuses.append(status)
    instance.send_header = lambda *args: None
    instance.end_headers = lambda: None
    instance.do_GET()
    assert statuses == [403]


def invoke_vercel(body, length=None):
    instance = object.__new__(poster.handler)
    instance.headers = {"Content-Length": str(len(body) if length is None else length)}
    instance.client_address = ("127.0.0.1", 1)
    instance.rfile = io.BytesIO(body)
    instance.wfile = io.BytesIO()
    instance._get_client_ip = lambda: "test"
    statuses, headers = [], {}
    instance.send_response = statuses.append
    instance.send_header = lambda name, value: headers.update({name.lower(): value})
    instance.end_headers = lambda: None
    instance.do_POST()
    return statuses[0], headers, instance.wfile.getvalue()


@pytest.mark.parametrize("body,status", [(b"[]", 400), (b"null", 400), (b"\xff", 400), (b'{"imageBase64":"eA=="}', 415)])
def test_vercel_input_status(body, status, monkeypatch):
    monkeypatch.setattr(poster._rate_limiter, "check", lambda ip: (True, 9))
    assert invoke_vercel(body)[0] == status


def test_vercel_private_response(monkeypatch):
    monkeypatch.setattr(poster._rate_limiter, "check", lambda ip: (True, 9))
    status, headers, body = invoke_vercel(json.dumps({"omerMode": True, "omerDay": 1}).encode())
    assert status == 200
    assert headers["cache-control"] == "private, no-store"


def test_static_symlink_escape_rejected(tmp_path, monkeypatch):
    import api.static
    root = tmp_path / "public"
    root.mkdir()
    secret = tmp_path / "secret"
    secret.write_text("private")
    (root / "asset").symlink_to(secret)
    monkeypatch.setattr(api.static, "PUBLIC_DIR", root)
    with pytest.raises(ValueError):
        api.static.resolve_static_path("/asset")


@pytest.mark.parametrize("length,status", [(4_400_001, 413), ("-1", 400), ("invalid", 400)])
def test_vercel_rejects_length_before_read(length, status, monkeypatch):
    monkeypatch.setattr(poster._rate_limiter, "check", lambda ip: (True, 9))
    assert invoke_vercel(b"", length)[0] == status


def test_omer_invalid_date_is_400(client):
    assert client.get("/omer-info?date=2025-02-30").status_code == 400


def test_adapter_stream_limit_without_content_length():
    import asyncio
    from starlette.requests import Request
    from poster_http import create_poster_response
    chunks = iter([{"type": "http.request", "body": b" " * (2_300_000), "more_body": True}] * 2)
    async def receive():
        return next(chunks)
    def forbidden(payload):
        pytest.fail("Oversized body reached poster generation")
    request = Request({"type": "http", "method": "POST", "path": "/poster", "headers": []}, receive)
    result = asyncio.run(create_poster_response(request, forbidden))
    assert result.status_code == 413


def test_http_response_limit(client, monkeypatch):
    monkeypatch.setattr(poster, "generate_poster", lambda **kwargs: b"x" * 4_400_001)
    result = client.post("/poster", json={})
    assert result.status_code == 413
    assert len(result.content) < 1000


def test_vercel_response_limit(monkeypatch):
    monkeypatch.setattr(poster._rate_limiter, "check", lambda ip: (True, 9))
    monkeypatch.setattr(poster, "generate_poster", lambda **kwargs: b"x" * 4_400_001)
    status, headers, body = invoke_vercel(b"{}")
    assert status == 413
    assert len(body) < 1000


def test_in_process_output_does_not_inherit_http_limit(monkeypatch):
    monkeypatch.setattr(poster, "generate_poster", lambda **kwargs: b"x" * 4_400_001)
    assert len(poster.build_poster_from_payload({})) == 4_400_001


def test_coordinate_city_without_offset_renders(client):
    result = client.post("/poster", json={
        "startDate": "2025-01-24",
        "cities": [{"name": "ירושלים", "lat": 31.779737, "lon": 35.209554}],
    })
    assert result.status_code == 200
    assert result.content.startswith(b"\x89PNG")


def test_vercel_coordinate_city_without_offset_renders(monkeypatch):
    monkeypatch.setattr(poster._rate_limiter, "check", lambda ip: (True, 9))
    status, headers, body = invoke_vercel(json.dumps({
        "startDate": "2025-01-24",
        "cities": [{"name": "ירושלים", "lat": 31.779737, "lon": 35.209554}],
    }).encode())
    assert status == 200
    assert body.startswith(b"\x89PNG")
