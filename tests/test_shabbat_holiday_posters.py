"""Regression coverage for whole holiday sequences, including rendered text."""

import unittest
from datetime import date
from io import BytesIO
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import patch

from PIL import Image

import hebcal_api
import make_shabbat_posts as posters
from calendar_utils import (
    _get_jewcal_with_location_cached,
    find_next_sequence,
    get_shabbat_in_sequence,
    jewcal_times_for_sequence,
)


class TestShabbatHolidayPosters(unittest.TestCase):
    def setUp(self):
        # Keep integration tests deterministic and independent of Hebcal uptime.
        self.api = patch('hebcal_api._get_hebcal_data_for_year', return_value=None)
        self.api.start()
        self.addCleanup(self.api.stop)

    def render(self, start):
        with TemporaryDirectory() as directory:
            background = Path(directory) / 'background.png'
            Image.new('RGB', (1080, 1080), '#8090a0').save(background)
            with patch.object(posters, 'draw_text_with_stroke',
                              wraps=posters.draw_text_with_stroke) as draw:
                result = posters.generate_poster(
                    image_path=str(background), start_date=start,
                    cities=posters.DEFAULT_CITIES[:1], date_format='gregorian',
                    show_watermark=False,
                )
            self.assertEqual(Image.open(BytesIO(result)).size, (1080, 1080))
            texts = [call.args[2] for call in draw.call_args_list]
            # Title, subtitle, three column headers, and one city row.
            self.assertEqual(len(texts), 8)
            return texts

    def test_rosh_hashana_2026(self):
        texts = self.render(date(2026, 9, 11))
        self.assertEqual(texts[:2], [
            'שבת שלום וחג שמח', 'ראש השנה | 11-13.09.2026',
        ])
        self.assertEqual(texts[2:5], ['עיר', 'הדלקת נרות', 'צאת החג'])

    def test_rosh_hashana_starting_sunday(self):
        texts = self.render(date(2029, 9, 7))
        self.assertEqual(texts[0], 'שבת שלום וחג שמח')
        self.assertIn('ראש השנה', texts[1])
        self.assertIn('7-10.09.2029', texts[1])
        self.assertEqual(texts[4], 'צאת החג')

    def test_one_day_festival_on_shabbat(self):
        texts = self.render(date(2026, 9, 25))
        self.assertEqual(texts[:2], [
            'שבת שלום וחג שמח', 'סוכות | 25-26.09.2026',
        ])
        self.assertEqual(texts[4], 'צאת השבת והחג')

    def test_pesach_on_shabbat(self):
        texts = self.render(date(2025, 4, 18))
        self.assertEqual(texts[:2], [
            'שבת שלום וחג כשר ושמח', 'שביעי של פסח | 18-19.04.2025',
        ])
        self.assertEqual(texts[4], 'צאת השבת והחג')

    def test_pesach_starting_sunday_preserves_regular_parsha(self):
        texts = self.render(date(2025, 4, 11))
        self.assertEqual(texts[0], 'שבת שלום וחג כשר ושמח')
        self.assertIn('פרשת צו', texts[1])
        self.assertIn('פסח', texts[1])
        self.assertEqual(texts[4], 'צאת החג')

    def test_yomtov_followed_by_shabbat_preserves_subtitle(self):
        texts = self.render(date(2026, 5, 21))
        self.assertEqual(texts[:2], [
            'שבת שלום וחג שמח', 'שבועות | 21-23.05.2026',
        ])
        self.assertEqual(texts[4], 'צאת השבת')

    def test_yom_kippur_on_shabbat(self):
        texts = self.render(date(2027, 10, 8))
        self.assertEqual(texts[:2], [
            'גמר חתימה טובה', 'יום כיפור | 8-9.10.2027',
        ])

    def test_weekday_rosh_hashana(self):
        texts = self.render(date(2025, 9, 22))
        self.assertEqual(texts[0], 'שנה טובה')
        self.assertEqual(texts[4], 'צאת החג')

    def test_regular_shabbat_unchanged(self):
        texts = self.render(date(2025, 1, 24))
        self.assertEqual(texts[:2], ['שבת שלום', 'פרשת וארא | 24-25.01.2025'])
        self.assertEqual(texts[2:5], ['עיר', 'כניסת שבת', 'צאת שבת'])

    def test_chol_hamoed_unchanged(self):
        texts = self.render(date(2026, 4, 3))
        self.assertEqual(texts[:2], [
            'שבת שלום', 'שבת חול המועד פסח | 3-4.04.2026',
        ])

    def test_only_first_candles_and_last_exit(self):
        city = posters.DEFAULT_CITIES[0]
        for start in (date(2026, 9, 11), date(2029, 9, 7),
                      date(2025, 4, 11), date(2026, 5, 21)):
            with self.subTest(start=start):
                first, last, _, _ = find_next_sequence(start)
                info = jewcal_times_for_sequence(
                    city['lat'], city['lon'], first, last, city['candle_offset'])
                first_calendar = _get_jewcal_with_location_cached(
                    first, False, city['lat'], city['lon'], city['candle_offset'])
                last_calendar = _get_jewcal_with_location_cached(
                    last, False, city['lat'], city['lon'], city['candle_offset'])
                self.assertEqual(info['candle'],
                                 first_calendar.zmanim.to_dict()['hadlokas_haneiros'])
                self.assertEqual(info['havdalah'],
                                 last_calendar.zmanim.to_dict()['tzeis_hakochavim'])
                texts = self.render(start)
                self.assertEqual(texts[6:], [posters.iso_to_hhmm(info['candle']),
                                            posters.iso_to_hhmm(info['havdalah'])])


class TestExactSaturdayParsha(unittest.TestCase):
    def test_shabbat_inside_sequence(self):
        self.assertEqual(get_shabbat_in_sequence(date(2026, 9, 11), date(2026, 9, 13)),
                         date(2026, 9, 12))
        self.assertIsNone(get_shabbat_in_sequence(date(2025, 9, 22), date(2025, 9, 24)))

    def test_no_previous_week_when_exact_reading_missing(self):
        data = {'items': [{'category': 'parashat', 'date': '2025-01-18',
                           'title': 'Parashat Shemot'}]}
        with patch('hebcal_api._get_hebcal_data_for_year', return_value=data), \
                patch.dict(hebcal_api._LOCAL_PARSHA_DATA, {}, clear=True):
            self.assertIsNone(hebcal_api.get_parsha_from_hebcal(date(2025, 1, 25)))

    def test_festival_reading_suppresses_stale_local_parsha(self):
        with patch('hebcal_api._get_hebcal_data_for_year', return_value=None), \
                patch.dict(hebcal_api._LOCAL_PARSHA_DATA,
                           {'2026-09-12': 'Nitzavim-Vayeilech'}):
            for day in (date(2026, 9, 11), date(2026, 9, 12)):
                self.assertIsNone(hebcal_api.get_parsha_from_hebcal(day))

    def test_shabbat_after_weekday_festival_has_its_own_parsha(self):
        with patch('hebcal_api._get_hebcal_data_for_year', return_value=None):
            self.assertEqual(hebcal_api.get_parsha_from_hebcal(date(2026, 5, 22)),
                             'פרשת נשא')


if __name__ == '__main__':
    unittest.main()
