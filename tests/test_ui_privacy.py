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


def test_attribution_has_readable_contrast_without_moving_watermark():
    from image_utils import add_calendar_attribution
    for color in ('white', 'black'):
        original = Image.new('RGB', (1080, 1080), color)
        result = add_calendar_attribution(original)
        assert ImageChops.difference(original, result).getbbox()
        # Attribution occupies only the top-left margin, leaving branding untouched.
        assert ImageChops.difference(original.crop((950, 950, 1080, 1080)), result.crop((950, 950, 1080, 1080))).getbbox() is None
        assert len(result.crop((8, 8, 650, 40)).getcolors(100000)) > 2


@pytest.mark.parametrize('mode', ['shabbat', 'omer'])
@pytest.mark.parametrize('animated', [False, True])
def test_exported_poster_attributes_each_frame(monkeypatch, mode, animated):
    import base64
    import make_shabbat_posts
    import image_utils
    from api.poster import build_poster_from_payload
    observed = []
    real = image_utils.add_calendar_attribution
    def record(img):
        observed.append(img.size)
        return real(img)
    monkeypatch.setattr(make_shabbat_posts, 'add_calendar_attribution', record)
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
        assert len(observed) == count
        for index in range(count):
            poster.seek(index)
            area = poster.convert('RGB').crop((8, 8, 650, 40))
            assert len(area.getcolors(100000)) > 2


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
    rule = re.search(r'\.media-limits, \.share-details\s*\{([^}]+)\}', html).group(1)
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
