"""
Unit tests for edge cases in the Shabbat poster generation system.

Tests cover:
- Invalid locations (extreme coordinates, null island)
- Timezone handling (various timezones, DST transitions)
- Date boundaries (year boundaries, leap years, Hebrew calendar edge cases)
- Error handling and graceful degradation
- Cities module edge cases
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
    jewcal_times_for_date,
    jewcal_times_for_sequence,
    iso_to_hhmm,
    translate_parsha,
    fix_hebrew,
    _get_saturday_for_date,
    CITIES,
)
from cities import (
    load_cities_from_geojson,
    get_cities_list,
    build_city_lookup,
    _get_candle_offset,
    DEFAULT_CANDLE_OFFSET,
    SPECIAL_OFFSET_CITIES,
)


class TestInvalidLocations(unittest.TestCase):
    """Tests for handling invalid or extreme locations."""

    def test_null_island_coordinates(self):
        """Test location at 0,0 (null island in Atlantic Ocean)."""
        null_lat, null_lon = 0.0, 0.0
        friday = date(2025, 1, 24)

        # Should not crash, but may return unusual times
        result = jewcal_times_for_date(null_lat, null_lon, friday, 20)
        self.assertIsInstance(result, dict)

    def test_extreme_north_location(self):
        """Test location at extreme north (near Arctic)."""
        arctic_lat, arctic_lon = 70.0, 25.0  # Northern Norway
        friday = date(2025, 1, 24)

        result = jewcal_times_for_date(arctic_lat, arctic_lon, friday, 20)
        self.assertIsInstance(result, dict)

    def test_southern_hemisphere_location(self):
        """Test location in southern hemisphere."""
        cape_town_lat, cape_town_lon = -33.92, 18.42  # Cape Town, South Africa
        friday = date(2025, 1, 24)

        result = jewcal_times_for_date(cape_town_lat, cape_town_lon, friday, 20)
        self.assertIsInstance(result, dict)

    def test_far_east_timezone(self):
        """Test location in far east timezone (e.g., Tokyo)."""
        tokyo_lat, tokyo_lon = 35.68, 139.69
        friday = date(2025, 1, 24)

        result = jewcal_times_for_date(tokyo_lat, tokyo_lon, friday, 20)
        self.assertIsInstance(result, dict)


class TestDateBoundaries(unittest.TestCase):
    """Tests for date boundary edge cases."""

    def test_year_boundary_crossing(self):
        """Test sequence that crosses year boundary."""
        dec_31 = date(2025, 12, 31)
        result = find_next_sequence(dec_31)
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 4)

    def test_leap_year_february(self):
        """Test date in leap year February."""
        leap_feb = date(2024, 2, 29)  # Leap year
        result = find_next_sequence(leap_feb)
        self.assertIsInstance(result, tuple)

    def test_far_future_date(self):
        """Test date far in the future."""
        future_date = date(2030, 6, 15)
        result = find_next_sequence(future_date)
        self.assertIsInstance(result, tuple)
        _, seq_end, _, _ = result
        # The sequence should end on or after the future_date
        # (start might be earlier if we're in the middle of a sequence)
        self.assertGreaterEqual(seq_end, future_date - timedelta(days=7))

    def test_very_old_date(self):
        """Test with a historical date."""
        old_date = date(2020, 1, 1)
        result = find_next_sequence(old_date)
        self.assertIsInstance(result, tuple)


class TestTimezoneEdgeCases(unittest.TestCase):
    """Tests for timezone handling edge cases."""

    def test_iso_to_hhmm_various_timezones(self):
        """Test ISO string conversion with various timezone offsets."""
        # UTC
        result_utc = iso_to_hhmm("2025-01-24T14:30:00Z")
        self.assertRegex(result_utc, r"^\d{2}:\d{2}$")

        # Positive offset (Israel)
        result_plus = iso_to_hhmm("2025-01-24T16:30:00+02:00")
        self.assertRegex(result_plus, r"^\d{2}:\d{2}$")

        # Negative offset (US East)
        result_minus = iso_to_hhmm("2025-01-24T09:30:00-05:00")
        self.assertRegex(result_minus, r"^\d{2}:\d{2}$")

    def test_iso_to_hhmm_dst_transition(self):
        """Test during daylight saving time transition."""
        # Israel DST ends late October
        dst_transition = "2025-10-26T02:30:00+02:00"
        result = iso_to_hhmm(dst_transition)
        self.assertRegex(result, r"^\d{2}:\d{2}$")


class TestCitiesModule(unittest.TestCase):
    """Tests for cities.py module edge cases."""

    def test_get_candle_offset_jerusalem(self):
        """Jerusalem should have 40-minute offset."""
        offset = _get_candle_offset("ירושלים")
        self.assertEqual(offset, 40)

    def test_get_candle_offset_haifa(self):
        """Haifa should have 30-minute offset."""
        offset = _get_candle_offset("חיפה")
        self.assertEqual(offset, 30)

    def test_get_candle_offset_unknown_city(self):
        """Unknown city should use default offset."""
        offset = _get_candle_offset("עיר_לא_קיימת")
        self.assertEqual(offset, DEFAULT_CANDLE_OFFSET)

    def test_load_cities_from_geojson_returns_tuple(self):
        """load_cities_from_geojson should return a tuple."""
        result = load_cities_from_geojson()
        self.assertIsInstance(result, tuple)

    def test_get_cities_list_returns_list(self):
        """get_cities_list should return a mutable list."""
        result = get_cities_list()
        self.assertIsInstance(result, list)
        # Should be modifiable (mutable)
        if result:
            original_len = len(result)
            result.append({"name": "test"})
            self.assertEqual(len(result), original_len + 1)

    def test_build_city_lookup_creates_dict(self):
        """build_city_lookup should create a name-to-city dictionary."""
        cities = get_cities_list()
        lookup = build_city_lookup(cities)
        self.assertIsInstance(lookup, dict)
        # All keys should be city names
        for name, city in lookup.items():
            self.assertEqual(name, city["name"])


class TestHebrewTextEdgeCases(unittest.TestCase):
    """Tests for Hebrew text handling edge cases."""

    def test_fix_hebrew_with_numbers(self):
        """fix_hebrew should handle mixed Hebrew and numbers."""
        result = fix_hebrew("שבת 2025")
        self.assertIsInstance(result, str)

    def test_fix_hebrew_with_english(self):
        """fix_hebrew should handle mixed Hebrew and English."""
        result = fix_hebrew("שבת Shabbat")
        self.assertIsInstance(result, str)

    def test_translate_parsha_with_special_chars(self):
        """translate_parsha should handle special characters."""
        result = translate_parsha("Beha'alotcha")
        self.assertIn("פרשת", result)

    def test_translate_parsha_double_parsha(self):
        """translate_parsha handles single parshas - double parshas not in dict."""
        # Double parshas like "Vayakhel-Pekudei" would need special handling
        result = translate_parsha("Vayakhel")
        self.assertEqual(result, "פרשת ויקהל")


class TestPosterGenerationEdgeCases(unittest.TestCase):
    """Tests for poster generation edge cases."""

    def test_sequence_spanning_multiple_days(self):
        """Test multi-day holiday sequence detection."""
        # Rosh Hashana spans 2 days
        rosh_hashana = date(2025, 9, 22)  # Approx Rosh Hashana 2025
        seq_start, seq_end, _, _ = find_next_sequence(rosh_hashana)

        self.assertIsInstance(seq_start, date)
        self.assertIsInstance(seq_end, date)

    def test_shabbat_during_yomtov(self):
        """Test when Shabbat falls during Yom Tov (Chol HaMoed)."""
        # Find a Chol HaMoed Shabbat
        sukkot_shabbat = date(2025, 10, 11)  # Shabbat during Sukkot 2025
        result = find_next_sequence(sukkot_shabbat)
        self.assertIsInstance(result, tuple)

    def test_saturday_for_date_sunday(self):
        """_get_saturday_for_date should find next Saturday from Sunday."""
        sunday = date(2025, 1, 26)  # Sunday
        result = _get_saturday_for_date(sunday)
        # Should return the following Saturday
        expected = date(2025, 2, 1)  # Saturday
        self.assertEqual(result, expected)
        self.assertEqual(result.weekday(), 5)


class TestErrorGracefulDegradation(unittest.TestCase):
    """Tests for graceful error handling."""

    def test_jewcal_times_with_negative_offset(self):
        """jewcal_times should handle unusual candle offset values."""
        city = CITIES[0]
        friday = date(2025, 1, 24)

        # Unusual but technically valid offset
        result = jewcal_times_for_date(city["lat"], city["lon"], friday, 0)
        self.assertIsInstance(result, dict)

    def test_jewcal_times_with_large_offset(self):
        """jewcal_times should handle large candle offset."""
        city = CITIES[0]
        friday = date(2025, 1, 24)

        result = jewcal_times_for_date(city["lat"], city["lon"], friday, 120)
        self.assertIsInstance(result, dict)

    @patch('cities.open')
    def test_load_cities_handles_file_error(self, mock_open):
        """load_cities_from_geojson should handle file read errors."""
        mock_open.side_effect = IOError("File not found")

        # Clear the cache first
        load_cities_from_geojson.cache_clear()

        result = load_cities_from_geojson("nonexistent.geojson")
        self.assertEqual(result, tuple())


class TestIntegrationScenarios(unittest.TestCase):
    """Integration tests for complete scenarios."""

    def test_full_year_sequence_finding(self):
        """Test finding sequences throughout a full year."""
        start_date = date(2025, 1, 1)
        sequences_found = 0
        current_date = start_date

        # Find first 5 sequences
        while sequences_found < 5 and current_date < date(2026, 1, 1):
            seq_start, seq_end, _, _ = find_next_sequence(current_date)
            self.assertGreaterEqual(seq_start, current_date)
            self.assertLessEqual(seq_start, seq_end)

            sequences_found += 1
            current_date = seq_end + timedelta(days=1)

        self.assertEqual(sequences_found, 5)

    def test_all_default_cities_valid(self):
        """All default CITIES should have valid coordinates."""
        for city in CITIES:
            self.assertIn("name", city)
            self.assertIn("lat", city)
            self.assertIn("lon", city)
            self.assertIn("candle_offset", city)

            # Verify coordinates are in valid ranges
            self.assertGreaterEqual(city["lat"], -90)
            self.assertLessEqual(city["lat"], 90)
            self.assertGreaterEqual(city["lon"], -180)
            self.assertLessEqual(city["lon"], 180)

            # Verify candle offset is reasonable
            self.assertGreaterEqual(city["candle_offset"], 0)
            self.assertLessEqual(city["candle_offset"], 60)


if __name__ == "__main__":
    unittest.main()

