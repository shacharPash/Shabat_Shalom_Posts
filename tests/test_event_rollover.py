"""Regressions for a cold process on Saturday night before Yom Kippur."""
import io
import unittest
import shutil
import subprocess
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytz

import calendar_utils as calendar
from api import upcoming_events


class EventRolloverTests(unittest.TestCase):
    def setUp(self):
        calendar.clear_jewcal_cache()
        self.addCleanup(calendar.clear_jewcal_cache)
        # Exercise the upstream behavior that historical-date tests miss:
        # today's location-aware JewCal rolls forward after nightfall.
        today = patch('jewcal.core.date_today', return_value=date(2026, 9, 19))
        night = patch('jewcal.models.zmanim.Zmanim.is_now_after_nightfall', return_value=True)
        today.start()
        night.start()
        self.addCleanup(today.stop)
        self.addCleanup(night.stop)
        offline = patch('hebcal_api._get_hebcal_data_for_year', return_value=None)
        offline.start()
        self.addCleanup(offline.stop)

    def test_explicit_dates_and_times_do_not_roll_forward_at_night(self):
        for lat, lon, offset in ((31.7683, 35.2137, 40), (32.08, 34.78, 20)):
            with self.subTest(lat=lat):
                actual = calendar._get_jewcal_with_location_cached(
                    date(2026, 9, 19), False, lat, lon, offset)
                self.assertEqual(actual.jewish_date.gregorian_date, date(2026, 9, 19))
                self.assertEqual(actual.events.action, 'Havdalah')
                self.assertIsNone(actual.events.yomtov)
                self.assertTrue(actual.zmanim.to_dict()['tzeis_hakochavim'].startswith('2026-09-19T'))
                self.assertIsNone(actual.zmanim.to_dict()['hadlokas_haneiros'])

    def test_havdalah_boundary_and_utc_input(self):
        actual = calendar._get_jewcal_with_location_cached(
            date(2026, 9, 19), False, 31.7683, 35.2137, 40)
        boundary = actual.zmanim.tzeis_hakochavim
        self.assertEqual(calendar.get_effective_start_date(boundary - timedelta(seconds=1)), date(2026, 9, 19))
        self.assertEqual(calendar.get_effective_start_date(boundary), date(2026, 9, 20))
        now = pytz.timezone('Asia/Jerusalem').localize(datetime(2026, 9, 19, 19, 55))
        self.assertEqual(calendar.get_effective_start_date(now.astimezone(timezone.utc)), date(2026, 9, 20))

    def test_upcoming_events_select_yom_kippur_after_shabbat(self):
        for hour, expected in ((18, ('2026-09-18', '2026-09-19')),
                               (19, ('2026-09-20', '2026-09-21'))):
            with self.subTest(hour=hour):
                now = datetime(2026, 9, 19, hour, 55)
                with patch.object(upcoming_events, 'get_effective_start_date',
                                  side_effect=lambda: calendar.get_effective_start_date(now)):
                    event = upcoming_events.get_upcoming_events()[0]
                self.assertEqual((event['startDate'], event['endDate']), expected)
                if hour == 19:
                    self.assertEqual(event['eventName'], 'Yom Kippur')

    def test_header_and_times_share_the_same_explicit_sequence(self):
        old = calendar.jewcal_times_for_sequence(31.7683, 35.2137,
              date(2026, 9, 18), date(2026, 9, 19), 40)
        self.assertEqual(old['event_type'], 'shabbos')
        self.assertTrue(old['havdalah'].startswith('2026-09-19T'))
        upcoming = calendar.jewcal_times_for_sequence(31.7683, 35.2137,
                   date(2026, 9, 20), date(2026, 9, 21), 40)
        self.assertEqual(upcoming['event_type'], 'yomtov')
        self.assertIn('Kippur', upcoming['event_name'])
        self.assertTrue(upcoming['candle'].startswith('2026-09-20T'))
        self.assertTrue(upcoming['havdalah'].startswith('2026-09-21T'))

    def test_upcoming_response_is_not_cached_across_havdalah(self):
        handler = object.__new__(upcoming_events.handler)
        handler.wfile = io.BytesIO()
        headers = {}
        handler.send_response = lambda status: self.assertEqual(status, 200)
        handler.send_header = lambda name, value: headers.update({name: value})
        handler.end_headers = lambda: None
        with patch.object(upcoming_events, 'get_upcoming_events', return_value=[]):
            handler.do_GET()
        self.assertEqual(headers['Cache-Control'], 'no-store')

    @unittest.skipUnless(shutil.which('node'), 'Node is required for UI regressions')
    def test_open_tab_refreshes_automatic_date_before_posting(self):
        result = subprocess.run(
            ['node', str(Path(__file__).with_name('event_rollover.cjs'))],
            capture_output=True, text=True, timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
