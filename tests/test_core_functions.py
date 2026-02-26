"""
Unit tests for core poster generation functionality.

Tests cover:
- Image processing functions (fit_background, fix_image_orientation)
- Text handling (fix_hebrew, translate_parsha, iso_to_hhmm)
- Font loading and text width calculations
- Poster composition
"""

import os
import sys
import unittest
from datetime import date
from io import BytesIO
from unittest.mock import patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image

from make_shabbat_posts import (
    translate_parsha,
    iso_to_hhmm,
    compose_poster,
    generate_poster,
    next_friday,
    CITIES,
    IMG_SIZE,
    PARASHA_TRANSLATION,
    _normalize_parsha_key,
)
from image_utils import (
    fix_hebrew,
    load_font,
    get_text_width,
    get_fitted_font,
    fix_image_orientation,
    fit_background,
)


class TestTextHelpers(unittest.TestCase):
    """Tests for text processing helper functions."""

    def test_fix_hebrew_empty_string(self):
        """fix_hebrew should handle empty strings."""
        result = fix_hebrew("")
        self.assertEqual(result, "")

    def test_fix_hebrew_none(self):
        """fix_hebrew should handle None input."""
        result = fix_hebrew(None)
        self.assertIsNone(result)

    def test_fix_hebrew_basic_text(self):
        """fix_hebrew should process Hebrew text."""
        result = fix_hebrew("שבת שלום")
        # The result should be a non-empty string (RTL processing)
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 0)


class TestParshaTranslation(unittest.TestCase):
    """Tests for parsha translation functionality."""

    def test_translate_known_parsha(self):
        """translate_parsha should return Hebrew for known parsha names."""
        result = translate_parsha("Bereshit")
        self.assertEqual(result, "פרשת בראשית")

    def test_translate_parsha_with_apostrophe(self):
        """translate_parsha should handle parshas with apostrophes."""
        result = translate_parsha("Ha'Azinu")
        self.assertEqual(result, "פרשת האזינו")

    def test_translate_parsha_with_hyphen(self):
        """translate_parsha should handle parshas with hyphens."""
        result = translate_parsha("Lech-Lecha")
        self.assertEqual(result, "פרשת לך לך")

    def test_translate_unknown_parsha(self):
        """translate_parsha should return original name for unknown parshas."""
        result = translate_parsha("UnknownParsha")
        self.assertEqual(result, "פרשת UnknownParsha")

    def test_translate_parsha_case_insensitive(self):
        """translate_parsha should be case-insensitive."""
        result = translate_parsha("bereshit")
        self.assertEqual(result, "פרשת בראשית")

    def test_normalize_parsha_key(self):
        """_normalize_parsha_key should remove punctuation and spaces."""
        self.assertEqual(_normalize_parsha_key("Ha'Azinu"), "haazinu")
        self.assertEqual(_normalize_parsha_key("Lech-Lecha"), "lechlecha")
        self.assertEqual(_normalize_parsha_key("Ki Tisa"), "kitisa")


class TestIsoToHhmm(unittest.TestCase):
    """Tests for ISO datetime to HH:MM conversion."""

    def test_iso_to_hhmm_valid_input(self):
        """iso_to_hhmm should convert valid ISO strings."""
        result = iso_to_hhmm("2025-01-24T16:30:00+02:00")
        # Should return a valid HH:MM format
        self.assertRegex(result, r"^\d{2}:\d{2}$")

    def test_iso_to_hhmm_empty_string(self):
        """iso_to_hhmm should return placeholder for empty string."""
        result = iso_to_hhmm("")
        self.assertEqual(result, "--:--")

    def test_iso_to_hhmm_none(self):
        """iso_to_hhmm should return placeholder for None."""
        result = iso_to_hhmm(None)
        self.assertEqual(result, "--:--")

    def test_iso_to_hhmm_invalid_format(self):
        """iso_to_hhmm should return placeholder for invalid format."""
        result = iso_to_hhmm("not-a-date")
        self.assertEqual(result, "--:--")

    def test_iso_to_hhmm_utc_timezone(self):
        """iso_to_hhmm should handle UTC (Z suffix) timezone."""
        result = iso_to_hhmm("2025-01-24T14:30:00Z")
        # Should convert to Israel time and return HH:MM
        self.assertRegex(result, r"^\d{2}:\d{2}$")


class TestFontLoading(unittest.TestCase):
    """Tests for font loading functionality."""

    def test_load_font_returns_font(self):
        """load_font should return a font object."""
        font = load_font(36)
        self.assertIsNotNone(font)

    def test_load_font_different_sizes(self):
        """load_font should work with different sizes."""
        font_small = load_font(20)
        font_large = load_font(100)
        self.assertIsNotNone(font_small)
        self.assertIsNotNone(font_large)

    def test_load_font_caching(self):
        """load_font should cache fonts for same parameters."""
        font1 = load_font(36, bold=False)
        font2 = load_font(36, bold=False)
        # Same cache key should return same object
        self.assertIs(font1, font2)


class TestNextFriday(unittest.TestCase):
    """Tests for next_friday date calculation."""

    def test_next_friday_from_monday(self):
        """next_friday should return the coming Friday from a Monday."""
        monday = date(2025, 12, 1)  # Monday
        result = next_friday(monday)
        self.assertEqual(result.weekday(), 4)  # Friday is weekday 4
        self.assertGreater(result, monday)

    def test_next_friday_from_friday(self):
        """next_friday from Friday should return same day or next week."""
        friday = date(2025, 12, 5)  # Friday
        result = next_friday(friday)
        self.assertEqual(result.weekday(), 4)

    def test_next_friday_from_saturday(self):
        """next_friday from Saturday should return the next Friday."""
        saturday = date(2025, 12, 6)  # Saturday
        result = next_friday(saturday)
        self.assertEqual(result.weekday(), 4)
        self.assertGreater(result, saturday)


class TestImageHelpers(unittest.TestCase):
    """Tests for image processing helper functions."""

    def test_fit_background_creates_correct_size(self):
        """fit_background should create image of correct size."""
        # Create a test image file
        test_img = Image.new("RGB", (800, 600), color="red")
        temp_path = "/tmp/test_image.png"
        test_img.save(temp_path)

        try:
            result = fit_background(temp_path, (1080, 1080))
            self.assertEqual(result.size, (1080, 1080))
            self.assertEqual(result.mode, "RGB")
        finally:
            os.remove(temp_path)

    def test_fit_background_different_sizes(self):
        """fit_background should work with various target sizes."""
        test_img = Image.new("RGB", (1920, 1080), color="blue")
        temp_path = "/tmp/test_image_wide.png"
        test_img.save(temp_path)

        try:
            result = fit_background(temp_path, (800, 800))
            self.assertEqual(result.size, (800, 800))
        finally:
            os.remove(temp_path)

    def test_fix_image_orientation_no_exif(self):
        """fix_image_orientation should handle images without EXIF."""
        test_img = Image.new("RGB", (100, 100), color="green")
        result = fix_image_orientation(test_img)
        self.assertEqual(result.size, (100, 100))


class TestGetTextWidth(unittest.TestCase):
    """Tests for text width calculation."""

    def test_get_text_width_returns_positive(self):
        """get_text_width should return positive width for non-empty text."""
        font = load_font(36)
        width = get_text_width("Hello World", font)
        self.assertGreater(width, 0)

    def test_get_text_width_empty_string(self):
        """get_text_width should handle empty string."""
        font = load_font(36)
        width = get_text_width("", font)
        self.assertEqual(width, 0)

    def test_get_text_width_rtl(self):
        """get_text_width should handle RTL text."""
        font = load_font(36)
        width = get_text_width("שבת שלום", font, rtl=True)
        self.assertGreater(width, 0)


class TestGetFittedFont(unittest.TestCase):
    """Tests for font fitting functionality."""

    def test_get_fitted_font_returns_font(self):
        """get_fitted_font should return a font object."""
        original_font = load_font(100)
        result = get_fitted_font("Short", original_font, 500)
        self.assertIsNotNone(result)

    def test_get_fitted_font_reduces_size_for_long_text(self):
        """get_fitted_font should reduce size for text that doesn't fit."""
        original_font = load_font(100)
        long_text = "This is a very long text that will not fit in a small width"
        result = get_fitted_font(long_text, original_font, 200, min_size=20)
        # Result font should have smaller or equal size
        self.assertLessEqual(result.size, original_font.size)


if __name__ == "__main__":
    unittest.main()

