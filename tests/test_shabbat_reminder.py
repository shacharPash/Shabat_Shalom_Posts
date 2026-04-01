"""
Unit tests for Shabbat reminder endpoint.

Tests cover:
- is_friday_or_erev_yomtov() returning True/False on various days
- force=true parameter bypasses the Friday/Erev Yom Tov check
- Normal schedule does not bypass the check
"""

import json
import os
import sys
import unittest
from datetime import date
from io import BytesIO
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.shabbat_reminder import is_friday_or_erev_yomtov


class TestIsFridayOrErevYomTov(unittest.TestCase):
    """Tests for is_friday_or_erev_yomtov() helper."""

    def test_friday_returns_true(self):
        """A Friday date should return True."""
        # 2025-01-24 is a Friday
        friday = date(2025, 1, 24)
        with patch("api.shabbat_reminder.date") as mock_date:
            mock_date.today.return_value = friday
            self.assertTrue(is_friday_or_erev_yomtov())

    def test_wednesday_returns_false_when_no_yomtov(self):
        """A regular Wednesday (no Yom Tov) should return False."""
        # 2025-01-22 is a Wednesday with no Yom Tov
        wednesday = date(2025, 1, 22)
        with patch("api.shabbat_reminder.date") as mock_date:
            mock_date.today.return_value = wednesday
            self.assertFalse(is_friday_or_erev_yomtov())


class TestShabbatReminderForceParameter(unittest.TestCase):
    """Tests that force=true bypasses the Friday/Erev Yom Tov check."""

    def _make_handler(self, path: str, auth: str = "Bearer test-secret"):
        """Create a handler instance with a mocked request for the given path."""
        from api.shabbat_reminder import handler

        # Build a minimal fake handler instance without actually starting a server
        instance = handler.__new__(handler)
        instance.path = path

        # Mock headers
        mock_headers = MagicMock()
        mock_headers.get = lambda key, default=None: auth if key == "Authorization" else default
        instance.headers = mock_headers

        # Mock response writing
        instance._response_code = None
        instance._response_headers = {}
        instance._response_body = b""

        def send_response(code):
            instance._response_code = code

        def send_header(key, value):
            instance._response_headers[key] = value

        def end_headers():
            pass

        output = BytesIO()

        def write(data):
            output.write(data)
            instance._response_body = output.getvalue()

        instance.send_response = send_response
        instance.send_header = send_header
        instance.end_headers = end_headers
        instance.wfile = MagicMock()
        instance.wfile.write = write

        return instance

    def test_force_true_sends_to_all_users_on_non_friday(self):
        """With force=true the endpoint should send reminders even on a non-Friday."""
        from api.shabbat_reminder import handler

        instance = self._make_handler("/api/shabbat_reminder?force=true")

        wednesday = date(2025, 1, 22)

        with patch("api.shabbat_reminder.CRON_SECRET", "test-secret"), \
             patch("api.shabbat_reminder.date") as mock_date, \
             patch("api.shabbat_reminder.get_users_with_shabbat_reminders_enabled", return_value=["111"]), \
             patch("api.shabbat_reminder.send_shabbat_reminder", return_value=True):
            mock_date.today.return_value = wednesday
            instance.do_GET()

        self.assertEqual(instance._response_code, 200)
        response = json.loads(instance._response_body)
        # Should NOT be "skipped" - force bypassed the day check
        self.assertNotEqual(response.get("status"), "skipped")
        self.assertEqual(response.get("status"), "completed")
        self.assertEqual(response.get("sent"), 1)

    def test_no_force_skips_on_non_friday(self):
        """Without force=true the endpoint should skip on a non-Friday."""
        instance = self._make_handler("/api/shabbat_reminder")

        wednesday = date(2025, 1, 22)

        with patch("api.shabbat_reminder.CRON_SECRET", "test-secret"), \
             patch("api.shabbat_reminder.date") as mock_date, \
             patch("api.shabbat_reminder.get_users_with_shabbat_reminders_enabled", return_value=["111"]), \
             patch("api.shabbat_reminder.send_shabbat_reminder", return_value=True):
            mock_date.today.return_value = wednesday
            instance.do_GET()

        self.assertEqual(instance._response_code, 200)
        response = json.loads(instance._response_body)
        self.assertEqual(response.get("status"), "skipped")

    def test_force_false_string_does_not_bypass(self):
        """force=false should NOT bypass the day check."""
        instance = self._make_handler("/api/shabbat_reminder?force=false")

        wednesday = date(2025, 1, 22)

        with patch("api.shabbat_reminder.CRON_SECRET", "test-secret"), \
             patch("api.shabbat_reminder.date") as mock_date, \
             patch("api.shabbat_reminder.get_users_with_shabbat_reminders_enabled", return_value=["111"]), \
             patch("api.shabbat_reminder.send_shabbat_reminder", return_value=True):
            mock_date.today.return_value = wednesday
            instance.do_GET()

        self.assertEqual(instance._response_code, 200)
        response = json.loads(instance._response_body)
        self.assertEqual(response.get("status"), "skipped")


if __name__ == "__main__":
    unittest.main()
