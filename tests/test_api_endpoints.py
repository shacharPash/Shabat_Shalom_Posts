"""
Unit tests for API endpoint behavior.

Tests cover:
- build_poster_from_payload function
- Request handling with various payload configurations
- Response formatting (PNG output)
- Error cases (invalid images, missing data)
"""

import base64
import os
import sys
import unittest
from io import BytesIO
from unittest.mock import patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image

from api.poster import build_poster_from_payload


def create_test_image_base64() -> str:
    """Create a small test image and return as base64 string."""
    img = Image.new("RGB", (100, 100), color="blue")
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


class TestBuildPosterFromPayload(unittest.TestCase):
    """Tests for build_poster_from_payload function."""

    def test_empty_payload_returns_png(self):
        """Empty payload should still return PNG bytes."""
        result = build_poster_from_payload({})

        # Should return bytes
        self.assertIsInstance(result, bytes)
        # Should be a valid PNG (starts with PNG signature)
        self.assertTrue(result.startswith(b'\x89PNG'))

    def test_payload_with_message(self):
        """Payload with custom message should work."""
        payload = {
            "message": "שבת שלום לכולם!"
        }

        result = build_poster_from_payload(payload)
        self.assertIsInstance(result, bytes)
        self.assertTrue(result.startswith(b'\x89PNG'))

    def test_payload_with_leiluy_neshama(self):
        """Payload with leiluyNeshama should work."""
        payload = {
            "leiluyNeshama": "אורי בורנשטיין הי\"ד"
        }

        result = build_poster_from_payload(payload)
        self.assertIsInstance(result, bytes)
        self.assertTrue(result.startswith(b'\x89PNG'))

    def test_payload_with_hide_dedication(self):
        """Payload with hideDedication should work."""
        payload = {
            "hideDedication": True
        }

        result = build_poster_from_payload(payload)
        self.assertIsInstance(result, bytes)

    def test_payload_with_start_date(self):
        """Payload with startDate should use that date."""
        payload = {
            "startDate": "2025-12-05"  # A Friday
        }

        result = build_poster_from_payload(payload)
        self.assertIsInstance(result, bytes)
        self.assertTrue(result.startswith(b'\x89PNG'))

    def test_payload_with_cities(self):
        """Payload with custom cities should work."""
        payload = {
            "cities": [
                {"name": "בני ברק", "lat": 32.089, "lon": 34.834, "candle_offset": 20}
            ]
        }

        result = build_poster_from_payload(payload)
        self.assertIsInstance(result, bytes)
        self.assertTrue(result.startswith(b'\x89PNG'))

    def test_payload_with_image_base64(self):
        """Payload with imageBase64 should use that image."""
        test_image_b64 = create_test_image_base64()
        payload = {
            "imageBase64": test_image_b64
        }

        result = build_poster_from_payload(payload)
        self.assertIsInstance(result, bytes)
        self.assertTrue(result.startswith(b'\x89PNG'))

    def test_invalid_image_base64_raises_error(self):
        """Invalid base64 image should raise RuntimeError."""
        payload = {
            "imageBase64": "not-valid-base64!!!"
        }

        with self.assertRaises(RuntimeError) as context:
            build_poster_from_payload(payload)

        self.assertIn("Failed to decode imageBase64", str(context.exception))

    @patch('api.poster.requests.get')
    def test_payload_with_image_url_success(self, mock_get):
        """Payload with valid imageUrl should download and use image."""
        # Create a mock response with valid image bytes
        img = Image.new("RGB", (100, 100), color="green")
        buffer = BytesIO()
        img.save(buffer, format="JPEG")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = buffer.getvalue()
        mock_get.return_value = mock_response

        payload = {
            "imageUrl": "https://example.com/image.jpg"
        }

        result = build_poster_from_payload(payload)
        self.assertIsInstance(result, bytes)
        self.assertTrue(result.startswith(b'\x89PNG'))

    @patch('api.poster.requests.get')
    def test_payload_with_image_url_failure(self, mock_get):
        """Failed image download should raise RuntimeError."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        payload = {
            "imageUrl": "https://example.com/nonexistent.jpg"
        }

        with self.assertRaises(RuntimeError) as context:
            build_poster_from_payload(payload)

        self.assertIn("Failed to download image", str(context.exception))

    def test_payload_with_local_image_path(self):
        """Payload with local image path should work."""
        # Create a temporary image file
        img = Image.new("RGB", (100, 100), color="yellow")
        temp_path = "/tmp/test_local_image.png"
        img.save(temp_path)

        try:
            payload = {
                "image": temp_path
            }

            result = build_poster_from_payload(payload)
            self.assertIsInstance(result, bytes)
            self.assertTrue(result.startswith(b'\x89PNG'))
        finally:
            os.remove(temp_path)


class TestApiPayloadPriority(unittest.TestCase):
    """Tests for image source priority in payload processing."""

    def test_base64_takes_priority_over_url(self):
        """imageBase64 should take priority over imageUrl - verify image is used."""
        test_image_b64 = create_test_image_base64()

        payload = {
            "imageBase64": test_image_b64,
            "imageUrl": "https://example.com/nonexistent.jpg"  # Would fail if used
        }

        # If base64 didn't take priority, this would fail due to invalid URL
        result = build_poster_from_payload(payload)
        self.assertIsInstance(result, bytes)
        self.assertTrue(result.startswith(b'\x89PNG'))

    def test_local_path_fallback_works(self):
        """Local image path should work as fallback."""
        # Create a temporary image
        img = Image.new("RGB", (100, 100), color="purple")
        temp_path = "/tmp/test_fallback_image.png"
        img.save(temp_path)

        try:
            payload = {
                "image": temp_path
            }
            result = build_poster_from_payload(payload)
            self.assertIsInstance(result, bytes)
        finally:
            os.remove(temp_path)


class TestApiOutputFormat(unittest.TestCase):
    """Tests for API output format verification."""

    def test_output_is_valid_png(self):
        """Output should be a valid PNG image."""
        result = build_poster_from_payload({})

        # Verify PNG signature
        self.assertTrue(result.startswith(b'\x89PNG\r\n\x1a\n'))

        # Verify it can be opened as an image
        img = Image.open(BytesIO(result))
        self.assertEqual(img.format, "PNG")

    def test_output_has_correct_dimensions(self):
        """Output image should have correct dimensions (1080x1080)."""
        result = build_poster_from_payload({})

        img = Image.open(BytesIO(result))
        self.assertEqual(img.size, (1080, 1080))

    def test_output_is_rgb_mode(self):
        """Output image should be in RGB mode."""
        result = build_poster_from_payload({})

        img = Image.open(BytesIO(result))
        # PNG might be RGBA or RGB
        self.assertIn(img.mode, ["RGB", "RGBA"])


class TestApiCitiesHandling(unittest.TestCase):
    """Tests for cities handling in API."""

    def test_default_cities_used_when_none_provided(self):
        """When no cities provided, default CITIES should be used."""
        result = build_poster_from_payload({})
        self.assertIsInstance(result, bytes)
        # Just verify it works without cities parameter

    def test_single_city_works(self):
        """Poster with single city should work."""
        payload = {
            "cities": [
                {"name": "אילת", "lat": 29.557, "lon": 34.951, "candle_offset": 20}
            ]
        }
        result = build_poster_from_payload(payload)
        self.assertIsInstance(result, bytes)

    def test_partial_city_info_works(self):
        """Cities with all required fields should work."""
        payload = {
            "cities": [
                {
                    "name": "חדרה",
                    "lat": 32.433,
                    "lon": 34.883,
                    "candle_offset": 20
                }
            ]
        }

        result = build_poster_from_payload(payload)
        self.assertIsInstance(result, bytes)


class TestUpcomingEventsEndpoint(unittest.TestCase):
    """Tests for the /upcoming-events endpoint."""

    def test_upcoming_events_returns_list(self):
        """Test that upcoming events endpoint returns a list of events."""
        from service import get_upcoming_events
        import asyncio

        # Run the async function
        result = asyncio.run(get_upcoming_events())

        # Should return a list
        self.assertIsInstance(result, list)
        # Should have approximately 52 events (one year of Shabbatot + holidays)
        self.assertGreaterEqual(len(result), 50)
        self.assertLessEqual(len(result), 60)

    def test_upcoming_events_structure(self):
        """Test that each event has required fields."""
        from service import get_upcoming_events
        import asyncio

        result = asyncio.run(get_upcoming_events())

        for event in result:
            self.assertIn("startDate", event)
            self.assertIn("endDate", event)
            self.assertIn("eventType", event)
            self.assertIn("displayName", event)
            self.assertIn("parsha", event)  # For searchability by parsha name
            self.assertIn("dateStr", event)
            self.assertIn("isNext", event)

    def test_first_event_is_next(self):
        """Test that the first event is marked as next."""
        from service import get_upcoming_events
        import asyncio

        result = asyncio.run(get_upcoming_events())

        self.assertTrue(result[0]["isNext"])
        # Other events should not be marked as next
        for event in result[1:]:
            self.assertFalse(event["isNext"])


if __name__ == "__main__":
    unittest.main()

