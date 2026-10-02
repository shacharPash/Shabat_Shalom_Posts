"""The shared greeting must be the title rendered in the poster."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from api import poster
from tests.test_local_routes import invoke_vercel


@pytest.mark.parametrize("payload, expected", [
    ({"startDate": "2025-01-24"}, "שבת שלום"),
    ({"startDate": "2026-10-02"}, "שבת שלום וחג שמח"),
    ({"startDate": "2026-10-02", "overrideMainTitle": "ברכה אישית"}, "ברכה אישית"),
])
def test_rendered_title_metadata(payload, expected):
    metadata = {}
    image = poster.build_poster_from_payload(payload, metadata=metadata)
    assert image.startswith(b"\x89PNG")
    assert metadata["title"] == expected


def test_vercel_share_title_header(monkeypatch):
    def render(payload, *, metadata):
        metadata["title"] = "שבת שלום וחג שמח"
        return b"\x89PNG"

    monkeypatch.setattr(poster, "build_poster_from_payload", render)
    monkeypatch.setattr(poster._rate_limiter, "check", lambda ip: (True, 9))
    status, headers, _ = invoke_vercel(b"{}")
    assert status == 200
    assert json.loads(headers["x-poster-title"]) == "שבת שלום וחג שמח"
    assert headers["access-control-expose-headers"] == "X-Poster-Title"


def test_whatsapp_share_browser_handler():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is required for browser handler checks")
    subprocess.run([node, str(Path(__file__).with_name("whatsapp_share.cjs"))], check=True)

