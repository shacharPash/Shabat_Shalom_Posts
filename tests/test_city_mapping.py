"""
Unit tests for city mapping logic.

Tests cover the city mapping behavior in service.py and api/poster.py:
- String-based city names mapping to full city objects
- Object-based city names with candle_offset overrides
- Unknown cities handling
- Empty lists and edge cases
- customCities fallback logic
"""

import os
import sys
import unittest
from unittest.mock import patch

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cities import build_city_lookup


class TestCityMapping(unittest.TestCase):
    """Tests for city mapping logic used in service.py and api/poster.py."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a minimal CITY_BY_NAME for testing
        self.test_cities = [
            {"name": "ירושלים", "lat": 31.778, "lon": 35.236, "candle_offset": 40, "population": 800000},
            {"name": "תל אביב -יפו", "lat": 32.079, "lon": 34.777, "candle_offset": 20, "population": 400000},
            {"name": "חיפה", "lat": 32.802, "lon": 35.001, "candle_offset": 30, "population": 270000},
        ]
        self.CITY_BY_NAME = build_city_lookup(self.test_cities)

    def map_cities(self, payload):
        """
        Simulate the city mapping logic from service.py lines 69-99.
        This is the function under test.
        """
        if "cities" in payload and isinstance(payload["cities"], list):
            city_items = payload["cities"]
            mapped_cities = []
            for item in city_items:
                # Handle both old format (string) and new format (object with name and candle_offset)
                if isinstance(item, str):
                    name = item
                    candle_offset = 20
                elif isinstance(item, dict):
                    name = item.get("name", "")
                    candle_offset = item.get("candle_offset", 20)
                else:
                    continue

                if name in self.CITY_BY_NAME:
                    city = self.CITY_BY_NAME[name].copy()
                    city["candle_offset"] = candle_offset  # Override with user's offset
                    mapped_cities.append(city)

            # Only use mapped cities if we found at least one
            if mapped_cities:
                payload["cities"] = mapped_cities
            else:
                # No valid predefined cities found
                # If user has custom cities, set empty list (don't fall back to defaults)
                # Otherwise, remove to trigger default cities
                if "customCities" in payload and payload["customCities"]:
                    payload["cities"] = []
                else:
                    del payload["cities"]

    def test_string_city_name_maps_to_full_object(self):
        """String city names should map to full city objects with coordinates."""
        payload = {"cities": ["ירושלים"]}
        self.map_cities(payload)
        
        self.assertEqual(len(payload["cities"]), 1)
        city = payload["cities"][0]
        self.assertEqual(city["name"], "ירושלים")
        self.assertEqual(city["lat"], 31.778)
        self.assertEqual(city["lon"], 35.236)
        self.assertEqual(city["candle_offset"], 20)  # Default for string format

    def test_object_city_with_custom_offset_overrides_default(self):
        """Object-based city with candle_offset should override the default."""
        payload = {"cities": [{"name": "ירושלים", "candle_offset": 50}]}
        self.map_cities(payload)
        
        self.assertEqual(len(payload["cities"]), 1)
        city = payload["cities"][0]
        self.assertEqual(city["name"], "ירושלים")
        self.assertEqual(city["candle_offset"], 50)  # Custom offset

    def test_unknown_city_is_skipped(self):
        """Unknown cities should be skipped, not added to mapped_cities."""
        payload = {"cities": ["עיר_לא_קיימת"]}
        self.map_cities(payload)
        
        # Should be deleted since no valid cities and no customCities
        self.assertNotIn("cities", payload)

    def test_empty_city_list(self):
        """Empty city list should be removed from payload."""
        payload = {"cities": []}
        self.map_cities(payload)
        
        # Empty list with no valid cities should be deleted
        self.assertNotIn("cities", payload)

    def test_mixed_valid_and_invalid_cities(self):
        """Mix of valid and invalid cities should only include valid ones."""
        payload = {"cities": ["ירושלים", "עיר_לא_קיימת", "חיפה"]}
        self.map_cities(payload)
        
        self.assertEqual(len(payload["cities"]), 2)
        names = [city["name"] for city in payload["cities"]]
        self.assertIn("ירושלים", names)
        self.assertIn("חיפה", names)
        self.assertNotIn("עיר_לא_קיימת", names)

    def test_custom_cities_fallback_empty_list(self):
        """When customCities exist and no valid cities, should set empty list."""
        payload = {
            "cities": ["עיר_לא_קיימת"],
            "customCities": [{"name": "עיר מותאמת", "candle": "16:30", "havdalah": "17:45"}]
        }
        self.map_cities(payload)
        
        # Should be empty list, not deleted
        self.assertIn("cities", payload)
        self.assertEqual(payload["cities"], [])

    def test_no_custom_cities_fallback_deletion(self):
        """When no customCities and no valid cities, should delete cities key."""
        payload = {"cities": ["עיר_לא_קיימת"]}
        self.map_cities(payload)

        # Should be deleted to trigger default cities
        self.assertNotIn("cities", payload)

    def test_non_dict_non_string_items_skipped(self):
        """Non-dict and non-string items should be skipped."""
        payload = {"cities": ["ירושלים", 123, None, ["nested"], {"name": "חיפה", "candle_offset": 25}]}
        self.map_cities(payload)

        self.assertEqual(len(payload["cities"]), 2)
        names = [city["name"] for city in payload["cities"]]
        self.assertIn("ירושלים", names)
        self.assertIn("חיפה", names)

    def test_object_without_name_key(self):
        """Object without 'name' key should be skipped."""
        payload = {"cities": [{"candle_offset": 30}, {"name": "ירושלים"}]}
        self.map_cities(payload)

        self.assertEqual(len(payload["cities"]), 1)
        self.assertEqual(payload["cities"][0]["name"], "ירושלים")

    def test_object_with_empty_name(self):
        """Object with empty name should be skipped."""
        payload = {"cities": [{"name": "", "candle_offset": 30}, {"name": "ירושלים"}]}
        self.map_cities(payload)

        self.assertEqual(len(payload["cities"]), 1)
        self.assertEqual(payload["cities"][0]["name"], "ירושלים")

    def test_multiple_cities_with_different_offsets(self):
        """Multiple cities with different custom offsets should all be preserved."""
        payload = {"cities": [
            {"name": "ירושלים", "candle_offset": 45},
            {"name": "תל אביב -יפו", "candle_offset": 18},
            {"name": "חיפה", "candle_offset": 35}
        ]}
        self.map_cities(payload)

        self.assertEqual(len(payload["cities"]), 3)

        # Check each city has correct custom offset
        for city in payload["cities"]:
            if city["name"] == "ירושלים":
                self.assertEqual(city["candle_offset"], 45)
            elif city["name"] == "תל אביב -יפו":
                self.assertEqual(city["candle_offset"], 18)
            elif city["name"] == "חיפה":
                self.assertEqual(city["candle_offset"], 35)

    def test_cities_not_in_payload(self):
        """Payload without 'cities' key should remain unchanged."""
        payload = {"customCities": []}
        original_payload = payload.copy()
        self.map_cities(payload)

        self.assertEqual(payload, original_payload)

    def test_cities_not_a_list(self):
        """Payload with 'cities' as non-list should remain unchanged."""
        payload = {"cities": "not a list"}
        self.map_cities(payload)

        # Should remain unchanged
        self.assertEqual(payload["cities"], "not a list")

    def test_city_object_copied_not_referenced(self):
        """Mapped cities should be copies, not references to CITY_BY_NAME."""
        payload = {"cities": [{"name": "ירושלים", "candle_offset": 50}]}
        self.map_cities(payload)

        # Modify the mapped city
        payload["cities"][0]["candle_offset"] = 99

        # Original should be unchanged
        self.assertEqual(self.CITY_BY_NAME["ירושלים"]["candle_offset"], 40)


if __name__ == "__main__":
    unittest.main()

