"""Focused frontend behavior and actual exported attribution regressions."""
import io
import shutil
import subprocess
from pathlib import Path

import pytest
from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parents[1]


def test_settings_link_node_regressions():
    node = shutil.which('node')
    assert node, 'Install Node 22 to run the frontend regression gate'
    result = subprocess.run([node, 'tests/ui_privacy.cjs'], cwd=ROOT, text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_png_metadata_preserves_pixels_without_copying_upload_text():
    from image_utils import CALENDAR_ATTRIBUTION, encode_poster_png
    for color in ('white', 'black'):
        original = Image.new('RGB', (1080, 1080), color)
        original.info['private-upload-note'] = 'must not be exported'
        with Image.open(io.BytesIO(encode_poster_png(original))) as result:
            assert ImageChops.difference(original, result).getbbox() is None
            assert result.info['Description'] == CALENDAR_ATTRIBUTION
            assert 'private-upload-note' not in result.info


@pytest.mark.parametrize('mode', ['shabbat', 'omer'])
@pytest.mark.parametrize('animated', [False, True])
def test_exported_poster_has_metadata_credit_and_clean_image(mode, animated):
    import base64
    from image_utils import CALENDAR_ATTRIBUTION
    from api.poster import build_poster_from_payload
    source = io.BytesIO()
    frames = [Image.new('RGB', (100, 100), c) for c in ('navy', 'green')]
    if animated:
        frames[0].save(source, format='GIF', save_all=True, append_images=frames[1:], duration=200, loop=0)
    else:
        frames[0].save(source, format='PNG')
    payload = {'startDate':'2026-05-01', 'cities':['ירושלים'], 'omerMode':mode == 'omer',
               'omerDay':29, 'omerDate':'2026-05-01', 'showWatermark':False,
               'imageBase64':base64.b64encode(source.getvalue()).decode()}
    result = build_poster_from_payload(payload)
    with Image.open(io.BytesIO(result)) as poster:
        count = getattr(poster, 'n_frames', 1)
        assert count == (2 if animated and mode == 'shabbat' else 1)
        credit = poster.info.get('Description') or poster.info['comment'].decode()
        assert credit == CALENDAR_ATTRIBUTION
        for index in range(count):
            poster.seek(index)
            pixels = poster.convert('RGB')
            # A solid background must have no text or black strip in its top margin.
            for y in range(8, 40):
                assert len(pixels.crop((8, y, 650, y + 1)).getcolors(10000)) == 1


@pytest.mark.parametrize('path', ['privacy.html', 'terms.html', 'fonts/Heebo.ttf', 'fonts/Heebo-OFL.txt', 'fonts/Alef-OFL.txt'])
def test_public_release_assets_available_in_local_app(path):
    from fastapi.testclient import TestClient
    from service import app
    with TestClient(app) as client:
        response = client.get('/' + path)
        assert response.status_code == 200
        assert len(response.content) > 100


def test_sharing_copy_has_readable_theme_contrast():
    """New explanatory text must not fall back to black in dark mode."""
    import re
    html = (ROOT / 'api/template.html').read_text()
    rule = re.search(r'\.share-details\s*\{([^}]+)\}', html).group(1)
    foreground_var = re.search(r'color:\s*var\((--[\w-]+)\)', rule).group(1)
    def luminance(color):
        channels = [int(color[i:i+2], 16) / 255 for i in (1, 3, 5)]
        linear = [c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4 for c in channels]
        return sum(c * weight for c, weight in zip(linear, (.2126, .7152, .0722)))
    for selector in (':root', '[data-theme="dark"]'):
        theme = re.search(re.escape(selector) + r'\s*\{([^}]+)\}', html).group(1)
        values = dict(re.findall(r'(--[\w-]+):\s*(#[0-9a-fA-F]{6})', theme))
        lights = sorted([luminance(values[foreground_var]), luminance(values['--container-bg'])])
        assert (lights[1] + .05) / (lights[0] + .05) >= 4.5
