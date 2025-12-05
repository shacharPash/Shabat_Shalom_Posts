"""
Test configuration and shared fixtures for Shabbat poster tests.

This module provides common test utilities and fixtures used across
all test modules.
"""

import os
import sys

# Ensure parent directory is in path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# Constants for test data
TEST_JERUSALEM = {
    "name": "ירושלים",
    "lat": 31.778117828230577,
    "lon": 35.23599222120022,
    "candle_offset": 40
}

TEST_TEL_AVIV = {
    "name": "תל אביב",
    "lat": 32.08680752114438,
    "lon": 34.78974135330866,
    "candle_offset": 20
}

# Known test dates
TEST_FRIDAY_JAN_2025 = "2025-01-24"  # Regular Shabbat
TEST_SATURDAY_JAN_2025 = "2025-01-25"  # Shabbat day
TEST_YOM_KIPPUR_2025 = "2025-10-02"  # Yom Kippur 2025
TEST_PESACH_2025 = "2025-04-12"  # First day of Pesach 2025

