#!/usr/bin/env python3
"""Validate complete Israel readings and atomically replace the local fallback."""
import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from collections.abc import Callable, Iterable
from datetime import date, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import requests
from jewcal import JewCal

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from translations import translate_parsha


def fetch_year(year: int) -> dict[str, Any]:
    url = ('https://www.hebcal.com/hebcal?v=1&cfg=json'
           f'&year={year}&month=x&ss=on&s=on&i=on')
    response = requests.get(url, timeout=(2, 3))
    try:
        response.raise_for_status()
        return response.json()
    finally:
        response.close()


def regular_saturdays(year: int) -> set[str]:
    """Enumerate Israel Saturdays, excluding festival Torah readings."""
    current = date(year, 1, 1)
    current += timedelta(days=(5 - current.weekday()) % 7)
    expected = set()
    while current.year == year:
        calendar = JewCal(gregorian_date=current, diaspora=False)
        festival = calendar.events.yomtov if calendar.has_events() else None
        if not festival or festival.startswith('Erev'):
            expected.add(current.isoformat())
        current += timedelta(days=7)
    return expected


def validate_year(data: dict[str, Any], year: int) -> dict[str, str]:
    if not isinstance(data, dict) or data.get('title') != f'Hebcal Israel {year}':
        raise ValueError(f'{year}: expected an Israel calendar response')
    items = data.get('items')
    if not isinstance(items, list):
        raise ValueError(f'{year}: missing calendar items')
    readings = {}
    for item in items:
        if not isinstance(item, dict):
            raise ValueError(f'{year}: malformed calendar item')
        if item.get('category') != 'parashat':
            continue
        day, title = item.get('date'), item.get('title')
        if not isinstance(day, str) or not isinstance(title, str):
            raise ValueError(f'{year}: malformed reading')
        parsed = date.fromisoformat(day)
        if parsed.isoformat() != day or parsed.year != year or parsed.weekday() != 5:
            raise ValueError(f'{year}: reading outside a Saturday in the requested year')
        if day in readings or not title.startswith('Parashat '):
            raise ValueError(f'{year}: duplicate or malformed reading')
        name = title.removeprefix('Parashat ').strip()
        if not name or re.search('[A-Za-z]', translate_parsha(name)):
            raise ValueError(f'{year}: unknown reading translation')
        readings[day] = name
    if readings.keys() != regular_saturdays(year):
        raise ValueError(f'{year}: missing or unexpected weekly readings')
    return readings


def update_parsha_data(years: Iterable[int], output: Path,
                       fetch_year: Callable[[int], dict[str, Any]] = fetch_year) -> int:
    years = sorted(set(years))
    if not years:
        raise ValueError('At least one year is required')
    if output.exists():
        existing = json.loads(output.read_text(encoding='utf-8'))
        if not isinstance(existing, dict):
            raise ValueError('Existing fallback must be a date mapping')
        if {date.fromisoformat(day).year for day in existing} - set(years):
            raise ValueError('Requested years would remove existing coverage')
    readings = {}
    # Any transport/validation failure exits before opening the destination.
    for year in years:
        readings.update(validate_year(fetch_year(year), year))
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8',
                                         dir=output.parent, prefix='.parsha-',
                                         suffix='.json', delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(dict(sorted(readings.items())), handle, ensure_ascii=False, indent=2)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return len(readings)


def cached_year_loader(directory: Path) -> Callable[[int], dict[str, Any]]:
    """Reuse official source responses after checking provenance and bytes."""
    manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
    entries = {entry['year']: entry for entry in manifest['years']}

    def load(year: int) -> dict[str, Any]:
        entry = entries[year]
        source = urlsplit(entry['source'])
        query = parse_qs(source.query)
        if (not entry.get('ok') or source.scheme != 'https' or
                source.netloc != 'www.hebcal.com' or source.path != '/hebcal' or
                query.get('i') != ['on'] or query.get('year') != [str(year)]):
            raise ValueError(f'{year}: invalid source provenance')
        content = (directory / f'{year}.json').read_bytes()
        if hashlib.sha256(content).hexdigest() != entry['sha256']:
            raise ValueError(f'{year}: source checksum mismatch')
        return json.loads(content)
    return load


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start-year', type=int, default=2024)
    parser.add_argument('--end-year', type=int, default=date.today().year + 20)
    parser.add_argument('--output', type=Path, default=Path('parsha_data.json'))
    parser.add_argument('--source-dir', type=Path, help='Validated cached official responses')
    args = parser.parse_args()
    loader = cached_year_loader(args.source_dir) if args.source_dir else fetch_year
    count = update_parsha_data(range(args.start_year, args.end_year + 1), args.output, loader)
    print(f'Validated {count} Israel readings through {args.end_year}')


if __name__ == '__main__':
    main()
