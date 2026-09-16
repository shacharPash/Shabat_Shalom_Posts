"""
Unit tests for API endpoint behavior.

Tests cover:
- build_poster_from_payload function
- Request handling with various payload configurations
- Response formatting (PNG output)
- Error cases (invalid images, missing data)
- Public remote-image rejection
- Telegram webhook secret validation
"""

import base64
import os
import sys
import unittest
import tempfile
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
        """Invalid base64 image is a public input error."""
        payload = {
            "imageBase64": "not-valid-base64!!!"
        }

        with self.assertRaises(ValueError):
            build_poster_from_payload(payload)

    def test_public_image_url_rejected(self):
        with self.assertRaises(ValueError):
            build_poster_from_payload({"imageUrl": "https://example.com/image.jpg"})

    def test_payload_with_local_image_path(self):
        """Payload with local image path should work."""
        # Create a temporary image file
        img = Image.new("RGB", (100, 100), color="yellow")
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        temp_path = os.path.join(directory.name, "local.png")
        img.save(temp_path)

        try:
            payload = {
                "image": temp_path
            }

            result = build_poster_from_payload(payload, allow_local_image=True)
            self.assertIsInstance(result, bytes)
            self.assertTrue(result.startswith(b'\x89PNG'))
        finally:
            os.remove(temp_path)


class TestApiPayloadPriority(unittest.TestCase):
    """Tests for image source priority in payload processing."""

    def test_forbidden_source_rejected_even_with_base64(self):
        payload = {"imageBase64": create_test_image_base64(), "imageUrl": "https://example.com/private"}
        with self.assertRaises(ValueError):
            build_poster_from_payload(payload)

    def test_local_path_fallback_works(self):
        """Local image path should work as fallback."""
        # Create a temporary image
        img = Image.new("RGB", (100, 100), color="purple")
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        temp_path = os.path.join(directory.name, "fallback.png")
        img.save(temp_path)

        try:
            payload = {
                "image": temp_path
            }
            result = build_poster_from_payload(payload, allow_local_image=True)
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
        from api.upcoming_events import get_upcoming_events

        result = get_upcoming_events()

        # Should return a list
        self.assertIsInstance(result, list)
        # Should have approximately 52 events (one year of Shabbatot + holidays)
        self.assertGreaterEqual(len(result), 50)
        self.assertLessEqual(len(result), 60)

    def test_upcoming_events_structure(self):
        """Test that each event has required fields."""
        from api.upcoming_events import get_upcoming_events

        result = get_upcoming_events()

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
        from api.upcoming_events import get_upcoming_events

        result = get_upcoming_events()

        self.assertTrue(result[0]["isNext"])
        # Other events should not be marked as next
        for event in result[1:]:
            self.assertFalse(event["isNext"])


class TestTelegramWebhookValidation(unittest.TestCase):
    """Tests for Telegram webhook secret validation."""

    def test_webhook_fails_closed_without_secret(self):
        """No incoming token is accepted when the server secret is missing."""
        import api.telegram_webhook

        with patch.object(api.telegram_webhook, "TELEGRAM_WEBHOOK_SECRET", None):
            self.assertFalse(api.telegram_webhook.is_valid_webhook_secret(None))
            self.assertFalse(api.telegram_webhook.is_valid_webhook_secret("attacker-token"))

    def test_webhook_secret_validation_logic(self):
        """Only an exact Telegram secret-token header is accepted."""
        import api.telegram_webhook

        with patch.object(api.telegram_webhook, "TELEGRAM_WEBHOOK_SECRET", "my-secret-token"):
            self.assertTrue(api.telegram_webhook.is_valid_webhook_secret("my-secret-token"))
            self.assertFalse(api.telegram_webhook.is_valid_webhook_secret("wrong-token"))
            self.assertFalse(api.telegram_webhook.is_valid_webhook_secret(None))

    @patch('requests.get', side_effect=AssertionError("Remote fetch attempted"))
    @patch('socket.getaddrinfo', side_effect=AssertionError("DNS lookup attempted"))
    def test_image_url_rejected_before_redirect_or_dns(self, lookup, fetch):
        """Rejecting URL input prevents redirects and DNS rebinding outright."""
        with self.assertRaises(ValueError):
            build_poster_from_payload({"imageUrl": "https://example.com/image.jpg"})


if __name__ == "__main__":
    unittest.main()

