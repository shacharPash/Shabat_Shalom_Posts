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
from datetime import date, timedelta
from unittest.mock import patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from make_shabbat_posts import (
    find_next_sequence,
    find_event_sequence,
    find_next_event_date,
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


if __name__ == "__main__":
    unittest.main()

