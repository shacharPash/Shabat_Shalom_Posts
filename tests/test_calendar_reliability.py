"""Calendar reliability regressions, using local data and mocked transport."""
import importlib
import json
import re
from datetime import date
from pathlib import Path
from unittest.mock import Mock

import pytest
import requests

import hebcal_api
from api import upcoming_events
from translations import translate_parsha


@pytest.fixture(autouse=True)
def reset_cache():
    hebcal_api.clear_hebcal_cache()
    yield
    hebcal_api.clear_hebcal_cache()


def test_israel_2027_fallback(monkeypatch):
    monkeypatch.setattr(hebcal_api.requests, 'get', Mock(side_effect=requests.Timeout))
    assert hebcal_api.get_parsha_from_hebcal(date(2027, 6, 19)) == 'פרשת בהעלותך'


def test_failure_cache_retries_after_monotonic_expiry(monkeypatch):
    now = [100.0]
    monkeypatch.setattr('time.monotonic', lambda: now[0])
    fetch = Mock(side_effect=requests.Timeout)
    monkeypatch.setattr(hebcal_api.requests, 'get', fetch)
    for _ in range(56):
        assert hebcal_api._get_hebcal_data_for_year(2027) is None
    assert fetch.call_count == 1
    assert sum(fetch.call_args.kwargs['timeout']) <= 5
    now[0] += 61
    hebcal_api._get_hebcal_data_for_year(2027)
    assert fetch.call_count == 2


def test_success_remains_cached_and_response_closed(monkeypatch):
    response = Mock()
    response.json.return_value = {'items': []}
    fetch = Mock(return_value=response)
    monkeypatch.setattr(hebcal_api.requests, 'get', fetch)
    assert hebcal_api._get_hebcal_data_for_year(2027) == {'items': []}
    assert hebcal_api._get_hebcal_data_for_year(2027) == {'items': []}
    fetch.assert_called_once()
    response.close.assert_called_once()


def test_upcoming_year_does_not_retry_failed_years_even_after_ttl(monkeypatch):
    class FixedDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 9, 15)
    monkeypatch.setattr(upcoming_events, 'get_effective_start_date', FixedDate.today)
    ticks = iter(range(0, 100000, 70))
    monkeypatch.setattr('time.monotonic', lambda: next(ticks))
    fetch = Mock(side_effect=requests.Timeout)
    monkeypatch.setattr(hebcal_api.requests, 'get', fetch)
    events = upcoming_events.get_upcoming_events()
    assert len(events) == 56
    assert fetch.call_count == 2


def test_upcoming_events_on_leap_day(monkeypatch):
    class LeapDate(date):
        @classmethod
        def today(cls):
            return cls(2028, 2, 29)
    monkeypatch.setattr(upcoming_events, 'get_effective_start_date', LeapDate.today)
    monkeypatch.setattr(hebcal_api.requests, 'get', Mock(side_effect=requests.Timeout))
    events = upcoming_events.get_upcoming_events()
    assert 50 <= len(events) <= 60
    assert events[0]['startDate'] >= '2028-02-29'
    assert events[-1]['startDate'] < '2029-03-07'


def year_payload(year=2025):
    data = json.loads(Path('parsha_data.json').read_text())
    return {'title': f'Hebcal Israel {year}', 'items': [
        {'date': day, 'category': 'parashat', 'title': f'Parashat {name}'}
        for day, name in data.items() if day.startswith(str(year))]}


@pytest.mark.parametrize('failure', ['total', 'partial', 'empty', 'missing_week', 'wrong_year', 'duplicate', 'unknown', 'diaspora'])
def test_generator_preserves_existing_file_on_any_invalid_year(tmp_path, failure):
    generator = importlib.import_module('scripts.update_parsha_data')
    output = tmp_path / 'parsha_data.json'
    original = b'{"2024-01-06": "Shemot", "2025-01-04": "Vayigash"}\n'
    output.write_bytes(original)
    valid = year_payload()
    if failure == 'empty':
        valid['items'] = []
    elif failure == 'missing_week':
        valid['items'].pop(10)
    elif failure == 'wrong_year':
        valid['items'][0]['date'] = '2026-01-03'
    elif failure == 'duplicate':
        valid['items'].append(valid['items'][0])
    elif failure == 'unknown':
        valid['items'][0]['title'] = 'Parashat Unknown'
    elif failure == 'diaspora':
        valid['title'] = 'Hebcal Diaspora 2025'
    def fetch(year):
        if failure == 'total' or (failure == 'partial' and year == 2025):
            raise requests.Timeout('offline')
        return year_payload(2024) if year == 2024 else valid
    with pytest.raises((ValueError, requests.RequestException)):
        generator.update_parsha_data([2024, 2025], output, fetch_year=fetch)
    assert output.read_bytes() == original
    assert list(tmp_path.iterdir()) == [output]


def test_generator_validates_and_replaces_atomically(tmp_path, monkeypatch):
    generator = importlib.import_module('scripts.update_parsha_data')
    output = tmp_path / 'parsha_data.json'
    output.write_text('{}')
    replace = generator.os.replace
    observed = []
    def replace_complete(source, destination):
        observed.append(json.loads(Path(source).read_text()))
        assert output.read_text() == '{}'
        replace(source, destination)
    monkeypatch.setattr(generator.os, 'replace', replace_complete)
    generator.update_parsha_data([2025], output, fetch_year=lambda year: year_payload(year))
    assert len(observed) == 1
    assert len(json.loads(output.read_text())) == 50
    assert list(tmp_path.iterdir()) == [output]


def test_generator_requests_israel_and_closes_response(monkeypatch):
    generator = importlib.import_module('scripts.update_parsha_data')
    response = Mock()
    response.json.return_value = year_payload()
    fetch = Mock(return_value=response)
    monkeypatch.setattr(generator.requests, 'get', fetch)
    generator.fetch_year(2025)
    assert 'i=on' in fetch.call_args.args[0]
    response.close.assert_called_once()


def test_all_bundled_readings_translate_and_cover_regular_saturdays():
    generator = importlib.import_module('scripts.update_parsha_data')
    data = json.loads(Path('parsha_data.json').read_text())
    assert len(data) == 836
    assert set(int(day[:4]) for day in data) == set(range(2024, 2041))
    for year in range(2024, 2041):
        generator.validate_year(year_payload(year), year)
    for day, name in data.items():
        assert date.fromisoformat(day).weekday() == 5
        assert not re.search('[A-Za-z]', translate_parsha(name))


def test_failure_cache_is_size_bounded(monkeypatch):
    monkeypatch.setattr(hebcal_api.requests, 'get', Mock(side_effect=requests.Timeout))
    monkeypatch.setattr('time.monotonic', lambda: 100)
    for year in range(2000, 2200):
        hebcal_api._get_hebcal_data_for_year(year)
    assert len(hebcal_api._failure_cache) <= 128


def test_request_sequence_does_not_leak_failure_to_next_request(monkeypatch):
    clock = [100]
    monkeypatch.setattr('time.monotonic', lambda: clock[0])
    fetch = Mock(side_effect=requests.Timeout)
    monkeypatch.setattr(hebcal_api.requests, 'get', fetch)
    with hebcal_api.hebcal_request_sequence():
        hebcal_api._get_hebcal_data_for_year(2027)
        clock[0] += 61
        hebcal_api._get_hebcal_data_for_year(2027)
    with hebcal_api.hebcal_request_sequence():
        hebcal_api._get_hebcal_data_for_year(2027)
    assert fetch.call_count == 2


@pytest.mark.parametrize('data', [None, [], {}, {'items': None}, {'items': [None]}])
def test_malformed_response_falls_back_and_is_failure_cached(monkeypatch, data):
    response = Mock()
    response.json.return_value = data
    fetch = Mock(return_value=response)
    monkeypatch.setattr(hebcal_api.requests, 'get', fetch)
    for _ in range(2):
        assert hebcal_api.get_parsha_from_hebcal(date(2027, 6, 19)) == 'פרשת בהעלותך'
    assert fetch.call_count == 1
    response.close.assert_called_once()


def test_generator_atomic_replace_failure_cleans_temp_and_keeps_old_file(tmp_path, monkeypatch):
    generator = importlib.import_module('scripts.update_parsha_data')
    output = tmp_path / 'parsha_data.json'
    output.write_text('{}')
    monkeypatch.setattr(generator.os, 'replace', Mock(side_effect=OSError('disk error')))
    with pytest.raises(OSError):
        generator.update_parsha_data([2025], output, fetch_year=lambda year: year_payload(year))
    assert output.read_text() == '{}'
    assert list(tmp_path.iterdir()) == [output]


def test_generator_refuses_to_drop_existing_years(tmp_path):
    generator = importlib.import_module('scripts.update_parsha_data')
    output = tmp_path / 'parsha_data.json'
    original = '{"2024-01-06":"Shemot"}'
    output.write_text(original)
    fetch = Mock()
    with pytest.raises(ValueError, match='remove existing coverage'):
        generator.update_parsha_data([2025], output, fetch_year=fetch)
    fetch.assert_not_called()
    assert output.read_text() == original


@pytest.mark.parametrize('tamper', ['hash', 'israel', 'year', 'host'])
def test_generator_rejects_unverified_cached_source(tmp_path, tamper):
    import hashlib
    generator = importlib.import_module('scripts.update_parsha_data')
    content = json.dumps(year_payload()).encode()
    (tmp_path / '2025.json').write_bytes(content)
    entry = {'year': 2025, 'ok': True,
             'source': 'https://www.hebcal.com/hebcal?year=2025&i=on',
             'sha256': hashlib.sha256(content).hexdigest()}
    if tamper == 'hash':
        entry['sha256'] = 'invalid'
    else:
        old, new = {'israel': ('i=on', 'i=off'), 'year': ('year=2025', 'year=2026'),
                    'host': ('www.hebcal.com', 'example.com')}[tamper]
        entry['source'] = entry['source'].replace(old, new)
    (tmp_path / 'manifest.json').write_text(json.dumps({'years': [entry]}))
    with pytest.raises(ValueError):
        generator.cached_year_loader(tmp_path)(2025)
