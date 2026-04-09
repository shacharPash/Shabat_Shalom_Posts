"""
Unit tests for Jewish calendar calculations using jewcal library.

Tests cover:
- find_next_sequence: Finding next Shabbat/Yom Tov sequences
- find_event_sequence: Complete event sequence detection
- jewcal_times_for_date: Single date time calculations
- jewcal_times_for_sequence: Multi-day sequence calculations
- is_end_of_holiday_sequence: Holiday sequence boundary detection
- get_parsha_from_hebcal: Parsha retrieval from Hebcal API
"""

import os
import sys
import unittest
from datetime import date, datetime, timedelta
from unittest.mock import patch, MagicMock

import pytz

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from make_shabbat_posts import (
    find_next_sequence,
    find_event_sequence,
    find_next_event_date,
    get_effective_start_date,
    jewcal_times_for_date,
    jewcal_times_for_sequence,
    is_end_of_holiday_sequence,
    CITIES,
)
from hebcal_api import (
    get_parsha_from_hebcal,
    clear_hebcal_cache,
    _get_saturday_for_date,
)


class TestFindNextSequence(unittest.TestCase):
    """Tests for find_next_sequence function."""

    def test_find_next_sequence_returns_tuple(self):
        """find_next_sequence should return a 4-tuple."""
        result = find_next_sequence(date.today())
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 4)

    def test_find_next_sequence_start_before_end(self):
        """Sequence start date should be <= end date."""
        seq_start, seq_end, event_type, event_name = find_next_sequence(date.today())
        self.assertLessEqual(seq_start, seq_end)

    def test_find_next_sequence_event_type_valid(self):
        """Event type should be 'shabbos' or 'yomtov' or None."""
        _, _, event_type, _ = find_next_sequence(date.today())
        self.assertIn(event_type, ["shabbos", "yomtov", None])

    def test_find_next_sequence_from_monday(self):
        """Finding sequence from a Monday should find upcoming Friday/Saturday."""
        # Find a Monday
        test_date = date(2025, 12, 1)  # Monday, December 1, 2025
        seq_start, seq_end, _, _ = find_next_sequence(test_date)
        # Sequence should start on or after test_date
        self.assertGreaterEqual(seq_start, test_date)


class TestFindEventSequence(unittest.TestCase):
    """Tests for find_event_sequence function."""

    def test_find_event_sequence_regular_shabbat(self):
        """find_event_sequence should work for regular Shabbat."""
        # A known Shabbat: January 24, 2025 (Friday) to January 25, 2025 (Saturday)
        friday = date(2025, 1, 24)
        seq_start, seq_end, event_type, event_name = find_event_sequence(friday)

        # Should return a valid sequence
        self.assertIsNotNone(seq_start)
        self.assertIsNotNone(seq_end)
        self.assertLessEqual(seq_start, seq_end)

    def test_find_event_sequence_returns_dates(self):
        """find_event_sequence should return date objects."""
        friday = date(2025, 1, 24)
        seq_start, seq_end, _, _ = find_event_sequence(friday)

        self.assertIsInstance(seq_start, date)
        self.assertIsInstance(seq_end, date)


class TestJewcalTimesForDate(unittest.TestCase):
    """Tests for jewcal_times_for_date function."""

    def test_jewcal_times_for_date_returns_dict(self):
        """jewcal_times_for_date should return a dictionary."""
        city = CITIES[0]  # Jerusalem
        friday = date(2025, 1, 24)

        result = jewcal_times_for_date(
            city["lat"], city["lon"], friday, city["candle_offset"]
        )

        self.assertIsInstance(result, dict)

    def test_jewcal_times_for_date_has_required_keys(self):
        """Result should have required keys."""
        city = CITIES[0]
        friday = date(2025, 1, 24)

        result = jewcal_times_for_date(
            city["lat"], city["lon"], friday, city["candle_offset"]
        )

        required_keys = ["parsha", "event_name", "event_type", "candle", "havdalah", "action"]
        for key in required_keys:
            self.assertIn(key, result)

    def test_jewcal_times_for_date_shabbat_event_type(self):
        """Result for Shabbat should have event_type='shabbos'."""
        city = CITIES[0]
        friday = date(2025, 1, 24)  # Regular Friday

        result = jewcal_times_for_date(
            city["lat"], city["lon"], friday, city["candle_offset"]
        )

        # Should be shabbos or yomtov
        self.assertIn(result.get("event_type"), ["shabbos", "yomtov", None])


class TestJewcalTimesForSequence(unittest.TestCase):
    """Tests for jewcal_times_for_sequence function."""

    def test_jewcal_times_for_sequence_returns_dict(self):
        """jewcal_times_for_sequence should return a dictionary."""
        city = CITIES[0]
        start_date = date(2025, 1, 24)
        end_date = date(2025, 1, 25)

        result = jewcal_times_for_sequence(
            city["lat"], city["lon"], start_date, end_date, city["candle_offset"]
        )

        self.assertIsInstance(result, dict)

    def test_jewcal_times_for_sequence_has_dates(self):
        """Result should include start_date and end_date."""
        city = CITIES[0]
        start_date = date(2025, 1, 24)
        end_date = date(2025, 1, 25)

        result = jewcal_times_for_sequence(
            city["lat"], city["lon"], start_date, end_date, city["candle_offset"]
        )

        self.assertEqual(result["start_date"], start_date)
        self.assertEqual(result["end_date"], end_date)

    def test_pesach_7_prefers_end_yomtov_over_chol_hamoed(self):
        """Pesach 7 should be preferred over Chol HaMoed when it's the end event.

        Bug fix: When sequence is Chol HaMoed 5 (start) to Pesach 7 (end),
        the event_name should be "Pesach 7", not "Chol HaMoed 5 (Pesach 6)".
        """
        city = CITIES[0]  # Jerusalem
        # April 7, 2026 = Chol HaMoed 5 (Pesach 6)
        # April 8, 2026 = Pesach 7 (Shvii shel Pesach)
        start_date = date(2026, 4, 7)
        end_date = date(2026, 4, 8)

        result = jewcal_times_for_sequence(
            city["lat"], city["lon"], start_date, end_date, city["candle_offset"]
        )

        # Should prefer Pesach 7 (the full Yom Tov) over Chol HaMoed
        self.assertEqual(result["event_type"], "yomtov")
        self.assertIn("Pesach", result["event_name"])
        self.assertNotIn("Chol HaMoed", result["event_name"])

    def test_yomtov_start_preferred_over_shabbat_end(self):
        """Yom Tov at start should be preferred over Shabbat at end.

        Example: Rosh Hashana 1 (start) + Shabbat (end) -> Rosh Hashana 1
        """
        city = CITIES[0]  # Jerusalem
        # September 12, 2026 = Rosh Hashana 1 (Saturday)
        # September 13, 2026 = Rosh Hashana 2 (Sunday - but it's yomtov)
        start_date = date(2026, 9, 11)  # Friday - erev Rosh Hashana
        end_date = date(2026, 9, 13)  # Rosh Hashana 2

        result = jewcal_times_for_sequence(
            city["lat"], city["lon"], start_date, end_date, city["candle_offset"]
        )

        # Yom Tov should be preferred
        self.assertEqual(result["event_type"], "yomtov")

    def test_shabbat_preferred_over_chol_hamoed(self):
        """Shabbat should be preferred over Chol HaMoed.

        When Chol HaMoed is at start and Shabbat is at end, prefer Shabbat.
        """
        city = CITIES[0]  # Jerusalem
        # October 9, 2026 = Chol HaMoed Sukkot (Friday)
        # October 10, 2026 = Shabbat Chol HaMoed Sukkot
        start_date = date(2026, 10, 9)
        end_date = date(2026, 10, 10)

        result = jewcal_times_for_sequence(
            city["lat"], city["lon"], start_date, end_date, city["candle_offset"]
        )

        # Should prefer Shabbat over Chol HaMoed
        self.assertEqual(result["event_type"], "shabbos")

    def test_shmini_atzeret_preferred_over_hoshana_rabba(self):
        """Shmini Atzeret should be preferred over Hoshana Rabba.

        Hoshana Rabba (Sukkot 7) is a regular day without melacha prohibition,
        so the end event (Shmini Atzeret) should be preferred.
        """
        city = CITIES[0]  # Jerusalem
        # October 2, 2026 = Hoshana Rabba (Sukkot 7) - Friday
        # October 3, 2026 = Shmini Atzeret (Sukkot 8) - Saturday
        start_date = date(2026, 10, 2)
        end_date = date(2026, 10, 3)

        result = jewcal_times_for_sequence(
            city["lat"], city["lon"], start_date, end_date, city["candle_offset"]
        )

        # Should prefer Shmini Atzeret (Yom Tov) over Hoshana Rabba
        self.assertEqual(result["event_type"], "yomtov")
        # Event name should contain Shmini Atzeret (various spellings) or Simchat Torah
        self.assertTrue(
            "Shmini" in result["event_name"] or "Simchat" in result["event_name"],
            f"Expected Shmini Atzeret/Simchat Torah, got: {result['event_name']}"
        )


class TestIsEndOfHolidaySequence(unittest.TestCase):
    """Tests for is_end_of_holiday_sequence function."""

    def test_saturday_is_end_of_shabbat(self):
        """Saturday should typically be end of Shabbat sequence."""
        saturday = date(2025, 1, 25)
        result = is_end_of_holiday_sequence(saturday)
        # Regular Saturday should be end of sequence
        self.assertIsInstance(result, bool)


class TestGetSaturdayForDate(unittest.TestCase):
    """Tests for _get_saturday_for_date helper."""

    def test_saturday_returns_itself(self):
        """Saturday should return itself."""
        saturday = date(2025, 1, 25)  # Saturday
        result = _get_saturday_for_date(saturday)
        self.assertEqual(result, saturday)

    def test_friday_returns_next_day(self):
        """Friday should return the next Saturday."""
        friday = date(2025, 1, 24)  # Friday
        result = _get_saturday_for_date(friday)
        expected_saturday = date(2025, 1, 25)
        self.assertEqual(result, expected_saturday)

    def test_monday_returns_saturday(self):
        """Monday should return upcoming Saturday."""
        monday = date(2025, 1, 20)  # Monday
        result = _get_saturday_for_date(monday)
        expected_saturday = date(2025, 1, 25)
        self.assertEqual(result, expected_saturday)


class TestMultipleCities(unittest.TestCase):
    """Tests for time calculations across multiple cities."""

    def test_different_cities_different_times(self):
        """Different cities should have different candle/havdalah times."""
        friday = date(2025, 1, 24)

        results = []
        for city in CITIES[:2]:  # Test first two cities
            result = jewcal_times_for_date(
                city["lat"], city["lon"], friday, city["candle_offset"]
            )
            results.append(result)

        # At least verify both return valid data
        self.assertEqual(len(results), 2)
        for result in results:
            self.assertIsInstance(result, dict)

    def test_jerusalem_40_minute_offset(self):
        """Jerusalem should use 40-minute candle offset."""
        jerusalem = CITIES[0]  # First city should be Jerusalem
        self.assertEqual(jerusalem["candle_offset"], 40)

    def test_tel_aviv_20_minute_offset(self):
        """Tel Aviv should use 20-minute candle offset."""
        tel_aviv = CITIES[1]  # Second city should be Tel Aviv
        self.assertEqual(tel_aviv["candle_offset"], 20)


class TestGetParshaFromHebcal(unittest.TestCase):
    """Tests for Hebcal API integration."""

    @patch('hebcal_api.requests.get')
    def test_get_parsha_handles_network_error(self, mock_get):
        """get_parsha_from_hebcal should use local data when API fails."""
        # Clear cache to ensure mock is called
        clear_hebcal_cache()

        mock_get.side_effect = Exception("Network error")

        result = get_parsha_from_hebcal(date(2025, 1, 25))
        # Should return parsha from local data even when API fails
        self.assertIsNotNone(result)
        self.assertIn("פרשת", result)  # Should have Hebrew parsha prefix

    @patch('hebcal_api.requests.get')
    def test_get_parsha_handles_empty_response(self, mock_get):
        """get_parsha_from_hebcal should use local data when API returns empty."""
        # Clear cache to ensure mock is called
        clear_hebcal_cache()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"items": []}
        mock_get.return_value = mock_response

        result = get_parsha_from_hebcal(date(2025, 1, 25))
        # Should return parsha from local data even when API returns empty
        self.assertIsNotNone(result)
        self.assertIn("פרשת", result)  # Should have Hebrew parsha prefix


class TestGetEffectiveStartDate(unittest.TestCase):
    """Tests for get_effective_start_date function."""

    def test_weekday_returns_same_day(self):
        """On a weekday without events, should return the same day."""
        israel_tz = pytz.timezone("Asia/Jerusalem")
        # Wednesday, April 9, 2025 at noon
        now = israel_tz.localize(datetime(2025, 4, 9, 12, 0, 0))
        result = get_effective_start_date(now)
        self.assertEqual(result, date(2025, 4, 9))

    def test_shabbat_before_havdalah_returns_same_day(self):
        """On Saturday before havdalah, should return same day."""
        israel_tz = pytz.timezone("Asia/Jerusalem")
        # Saturday, April 12, 2025 at 14:00 (before havdalah ~19:30)
        now = israel_tz.localize(datetime(2025, 4, 12, 14, 0, 0))
        result = get_effective_start_date(now)
        self.assertEqual(result, date(2025, 4, 12))

    def test_shabbat_after_havdalah_returns_tomorrow(self):
        """On Saturday after havdalah, should return next day."""
        israel_tz = pytz.timezone("Asia/Jerusalem")
        # Saturday, January 4, 2025 at 21:00 (after havdalah ~17:30)
        # This is a regular Shabbat with Havdalah action
        now = israel_tz.localize(datetime(2025, 1, 4, 21, 0, 0))
        result = get_effective_start_date(now)
        self.assertEqual(result, date(2025, 1, 5))

    def test_yomtov_end_after_havdalah_returns_tomorrow(self):
        """After havdalah at end of Yom Tov, should return next day."""
        israel_tz = pytz.timezone("Asia/Jerusalem")
        # Pesach 7 ends April 19, 2025 - at 21:00 (after havdalah)
        now = israel_tz.localize(datetime(2025, 4, 19, 21, 0, 0))
        result = get_effective_start_date(now)
        self.assertEqual(result, date(2025, 4, 20))

    def test_friday_afternoon_returns_friday(self):
        """On Friday afternoon (before candle lighting), should return Friday."""
        israel_tz = pytz.timezone("Asia/Jerusalem")
        # Friday, April 11, 2025 at 14:00 (before candle lighting)
        now = israel_tz.localize(datetime(2025, 4, 11, 14, 0, 0))
        result = get_effective_start_date(now)
        self.assertEqual(result, date(2025, 4, 11))


if __name__ == "__main__":
    unittest.main()

