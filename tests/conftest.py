"""
Test configuration and shared fixtures for Shabbat poster tests.

This module provides common test utilities and fixtures used across
all test modules.
"""

import os
import sys
import socket

import pytest
import requests

# Clear secrets before application modules are imported during collection.
for secret_name in ('TELEGRAM_BOT_TOKEN', 'TELEGRAM_WEBHOOK_SECRET', 'CRON_SECRET', 'REDIS_URL', 'KV_URL'):
    os.environ.pop(secret_name, None)


@pytest.fixture(autouse=True)
def offline_boundaries(monkeypatch):
    """Tests explicitly mock transport and DNS. The Redis fixture owns one socket."""
    def reject_request(*args, **kwargs):
        raise requests.ConnectionError('Tests require an explicit HTTP mock')

    def reject_socket(*args, **kwargs):
        raise OSError('Tests require an explicit network or DNS mock')

    monkeypatch.setattr(requests.sessions.Session, 'request', reject_request)
    monkeypatch.setattr(socket, 'getaddrinfo', reject_socket)
    monkeypatch.setattr(socket.socket, 'connect', reject_socket)
    monkeypatch.setattr(socket.socket, 'connect_ex', reject_socket)


@pytest.fixture(autouse=True)
def isolated_calendar_cache():
    import hebcal_api
    hebcal_api.clear_hebcal_cache()
    yield
    hebcal_api.clear_hebcal_cache()

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

