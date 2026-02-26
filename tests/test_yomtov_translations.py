"""
Unit tests for Yom Tov translation functionality.

Tests cover:
- Exact match translations (e.g., "Rosh Hashana" → "ראש השנה")
- Partial/prefix match translations (e.g., "Pesach I" → "פסח")
- Unknown event names (should return original)
- Special case: Chol HaMoed on Shabbat
"""

import os
import sys
import unittest
from datetime import date

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the canonical translation dictionary from the shared module
from translations import YOMTOV_TRANSLATIONS


def translate_yomtov(event_name):
    """
    Translate Yom Tov event name to Hebrew.
    
    This function replicates the logic from service.py and api/upcoming-events.py:
    1. Try exact match first
    2. Try prefix matching for variations like "Pesach I", "Sukkot II"
    3. Return original if no match found
    
    Args:
        event_name: English event name
        
    Returns:
        Hebrew translation or original name if not found
    """
    # Try exact match first
    display_name = YOMTOV_TRANSLATIONS.get(event_name)
    if not display_name:
        # Try matching prefix (for "Pesach I", "Sukkot II", etc.)
        for eng, heb in YOMTOV_TRANSLATIONS.items():
            if event_name.startswith(eng):
                display_name = heb
                break
        else:
            display_name = event_name
    return display_name


def translate_yomtov_with_shabbat_check(event_name, is_shabbat=False):
    """
    Translate Yom Tov event name with special handling for Chol HaMoed on Shabbat.
    
    Args:
        event_name: English event name
        is_shabbat: Whether the event falls on Shabbat (Saturday)
        
    Returns:
        Hebrew translation with special case for Chol HaMoed on Shabbat
    """
    display_name = translate_yomtov(event_name)
    
    # For Chol HaMoed on Shabbat (Saturday), show "שבת חול המועד"
    if "Chol HaMoed" in event_name and is_shabbat:
        display_name = "שבת חול המועד"
    
    return display_name


class TestYomTovExactMatches(unittest.TestCase):
    """Tests for exact match translations."""

    def test_rosh_hashana(self):
        """Rosh Hashana should translate correctly."""
        self.assertEqual(translate_yomtov("Rosh Hashana"), "ראש השנה")
        self.assertEqual(translate_yomtov("Rosh Hashanah"), "ראש השנה")

    def test_yom_kippur(self):
        """Yom Kippur should translate correctly."""
        self.assertEqual(translate_yomtov("Yom Kippur"), "יום כיפור")

    def test_sukkot_variations(self):
        """Sukkot variations should translate correctly."""
        self.assertEqual(translate_yomtov("Sukkot"), "סוכות")
        self.assertEqual(translate_yomtov("Sukkos"), "סוכות")

    def test_pesach_variations(self):
        """Pesach variations should translate correctly."""
        self.assertEqual(translate_yomtov("Pesach"), "פסח")
        self.assertEqual(translate_yomtov("Passover"), "פסח")

    def test_shavuot_variations(self):
        """Shavuot variations should translate correctly."""
        self.assertEqual(translate_yomtov("Shavuot"), "שבועות")
        self.assertEqual(translate_yomtov("Shavuos"), "שבועות")

    def test_chanukah_variations(self):
        """Chanukah variations should translate correctly."""
        self.assertEqual(translate_yomtov("Chanukah"), "חנוכה")
        self.assertEqual(translate_yomtov("Hanukkah"), "חנוכה")

    def test_purim(self):
        """Purim should translate correctly."""
        self.assertEqual(translate_yomtov("Purim"), "פורים")

    def test_minor_holidays(self):
        """Minor holidays should translate correctly."""
        self.assertEqual(translate_yomtov("Tu BiShvat"), "ט״ו בשבט")
        self.assertEqual(translate_yomtov("Tu B'Shvat"), "ט״ו בשבט")
        self.assertEqual(translate_yomtov("Lag BaOmer"), "ל״ג בעומר")
        self.assertEqual(translate_yomtov("Lag B'Omer"), "ל״ג בעומר")
        self.assertEqual(translate_yomtov("Tisha B'Av"), "תשעה באב")

    def test_israeli_holidays(self):
        """Israeli holidays should translate correctly."""
        self.assertEqual(translate_yomtov("Yom HaShoah"), "יום השואה")
        self.assertEqual(translate_yomtov("Yom HaZikaron"), "יום הזיכרון")
        self.assertEqual(translate_yomtov("Yom HaAtzmaut"), "יום העצמאות")
        self.assertEqual(translate_yomtov("Yom Yerushalayim"), "יום ירושלים")

    def test_shmini_atzeret_variations(self):
        """Shmini Atzeret variations should translate correctly."""
        self.assertEqual(translate_yomtov("Shmini Atzeret"), "שמיני עצרת")
        self.assertEqual(translate_yomtov("Shmini Atzeres"), "שמיני עצרת")
        self.assertEqual(translate_yomtov("Shemini Atzeret"), "שמיני עצרת")

    def test_simchat_torah_variations(self):
        """Simchat Torah variations should translate correctly."""
        self.assertEqual(translate_yomtov("Simchat Torah"), "שמחת תורה")
        self.assertEqual(translate_yomtov("Simchas Torah"), "שמחת תורה")
        self.assertEqual(translate_yomtov("Simchat Tora"), "שמחת תורה")

    def test_combined_holiday(self):
        """Combined holiday name should translate correctly."""
        self.assertEqual(
            translate_yomtov("Shmini Atzeret / Simchat Tora"),
            "שמיני עצרת / שמחת תורה"
        )


class TestYomTovPrefixMatches(unittest.TestCase):
    """Tests for prefix/partial match translations."""

    def test_pesach_with_day_number(self):
        """Pesach with day numbers should match prefix."""
        self.assertEqual(translate_yomtov("Pesach I"), "פסח")
        self.assertEqual(translate_yomtov("Pesach II"), "פסח")
        self.assertEqual(translate_yomtov("Pesach 1"), "פסח")
        self.assertEqual(translate_yomtov("Pesach 7"), "פסח")

    def test_sukkot_with_day_number(self):
        """Sukkot with day numbers should match prefix."""
        self.assertEqual(translate_yomtov("Sukkot I"), "סוכות")
        self.assertEqual(translate_yomtov("Sukkot II"), "סוכות")
        self.assertEqual(translate_yomtov("Sukkot 1"), "סוכות")
        self.assertEqual(translate_yomtov("Sukkos 1"), "סוכות")

    def test_shavuot_with_day_number(self):
        """Shavuot with day numbers should match prefix."""
        self.assertEqual(translate_yomtov("Shavuot I"), "שבועות")
        self.assertEqual(translate_yomtov("Shavuot 1"), "שבועות")
        self.assertEqual(translate_yomtov("Shavuos 1"), "שבועות")

    def test_rosh_hashana_with_day_number(self):
        """Rosh Hashana with day numbers should match prefix."""
        self.assertEqual(translate_yomtov("Rosh Hashana I"), "ראש השנה")
        self.assertEqual(translate_yomtov("Rosh Hashana 1"), "ראש השנה")
        self.assertEqual(translate_yomtov("Rosh Hashanah 2"), "ראש השנה")

    def test_prefix_match_with_extra_text(self):
        """Prefix matching should work with additional text."""
        # "Pesach" is in the dictionary, so "Pesach (some extra)" should match
        self.assertEqual(translate_yomtov("Pesach (extra)"), "פסח")
        self.assertEqual(translate_yomtov("Sukkot - Day 3"), "סוכות")


class TestYomTovUnknownEvents(unittest.TestCase):
    """Tests for unknown event names."""

    def test_unknown_event_returns_original(self):
        """Unknown event names should return the original name."""
        self.assertEqual(translate_yomtov("Unknown Holiday"), "Unknown Holiday")
        self.assertEqual(translate_yomtov("Some Random Event"), "Some Random Event")

    def test_empty_string(self):
        """Empty string should return empty string."""
        self.assertEqual(translate_yomtov(""), "")

    def test_partial_match_not_at_start(self):
        """Partial match not at start should return original."""
        # "Pesach" is in the middle, not at the start
        self.assertEqual(translate_yomtov("Before Pesach"), "Before Pesach")


class TestCholHaMoedSpecialCase(unittest.TestCase):
    """Tests for Chol HaMoed special case on Shabbat."""

    def test_chol_hamoed_on_shabbat(self):
        """Chol HaMoed on Shabbat should show special text."""
        result = translate_yomtov_with_shabbat_check("Chol HaMoed", is_shabbat=True)
        self.assertEqual(result, "שבת חול המועד")

    def test_chol_hamoed_not_on_shabbat(self):
        """Chol HaMoed not on Shabbat should show regular translation."""
        result = translate_yomtov_with_shabbat_check("Chol HaMoed", is_shabbat=False)
        self.assertEqual(result, "חול המועד")

    def test_chol_hamoed_with_number_on_shabbat(self):
        """Chol HaMoed with day number on Shabbat should show special text."""
        result = translate_yomtov_with_shabbat_check("Chol HaMoed 1", is_shabbat=True)
        self.assertEqual(result, "שבת חול המועד")

    def test_chol_hamoed_sukkot_on_shabbat(self):
        """Chol HaMoed Sukkot on Shabbat should show special text."""
        result = translate_yomtov_with_shabbat_check(
            "Chol HaMoed 1 (Sukkot 2)", is_shabbat=True
        )
        self.assertEqual(result, "שבת חול המועד")

    def test_other_holiday_on_shabbat_unchanged(self):
        """Other holidays on Shabbat should not be affected."""
        result = translate_yomtov_with_shabbat_check("Pesach", is_shabbat=True)
        self.assertEqual(result, "פסח")


class TestTranslationConsistency(unittest.TestCase):
    """Tests to ensure translation consistency across the codebase."""

    def test_all_dictionary_keys_translate(self):
        """All keys in the translation dictionary should translate to themselves."""
        for eng_name, heb_name in YOMTOV_TRANSLATIONS.items():
            result = translate_yomtov(eng_name)
            self.assertEqual(
                result, heb_name,
                f"Translation mismatch for '{eng_name}': expected '{heb_name}', got '{result}'"
            )

    def test_case_sensitivity(self):
        """Translation should be case-sensitive (as per current implementation)."""
        # Current implementation is case-sensitive
        self.assertEqual(translate_yomtov("Pesach"), "פסח")
        # Lowercase should not match (returns original)
        self.assertEqual(translate_yomtov("pesach"), "pesach")


if __name__ == "__main__":
    unittest.main()


