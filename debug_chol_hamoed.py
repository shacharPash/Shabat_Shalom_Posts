#!/usr/bin/env python3
"""
Debug script to analyze why the poster isn't updating for 2026-04-04.
Prints all relevant variables: event_type, event_name, seq_start, seq_end,
seq_end.weekday(), parsha, is_shabbat_chol_hamoed.
"""

from datetime import date, timedelta
from jewcal import JewCal
from calendar_utils import find_next_sequence, jewcal_times_for_sequence
from hebcal_api import get_parsha_from_hebcal

# Debug date: 2026-04-04 (שבת חול המועד פסח)
TARGET_DATE = date(2026, 4, 4)

print("=" * 60)
print(f"Debug Analysis for: {TARGET_DATE}")
print("=" * 60)

# Step 1: Check what JewCal sees for this date
print("\n📅 JewCal Analysis:")
jewcal_obj = JewCal(gregorian_date=TARGET_DATE, diaspora=False)
print(f"  has_events(): {jewcal_obj.has_events()}")
if jewcal_obj.has_events():
    print(f"  events.yomtov: {jewcal_obj.events.yomtov}")
    print(f"  events.shabbos: {jewcal_obj.events.shabbos}")
    print(f"  events.action: {jewcal_obj.events.action}")
    # print(f"  events.name: {jewcal_obj.events.name}")  # Not available

# Check the Hebrew date
try:
    print(f"  Hebrew date: {jewcal_obj.hebrew_date}")
except AttributeError:
    pass  # Not available in this jewcal version

# Step 2: Find the event sequence
print("\n🔍 find_next_sequence() Analysis:")
seq_start, seq_end, event_type, event_name = find_next_sequence(TARGET_DATE)
print(f"  seq_start: {seq_start} (weekday={seq_start.weekday()})")
print(f"  seq_end: {seq_end} (weekday={seq_end.weekday()})")
print(f"  event_type: {event_type}")
print(f"  event_name: {event_name}")

# Weekday meanings: 0=Monday, 1=Tuesday, ..., 4=Friday, 5=Saturday, 6=Sunday
weekday_names = {0: "Monday", 1: "Tuesday", 2: "Wednesday", 3: "Thursday", 
                 4: "Friday", 5: "Saturday", 6: "Sunday"}
print(f"  seq_end.weekday() == 5 (Saturday)? {seq_end.weekday() == 5} ({weekday_names[seq_end.weekday()]})")

# Step 3: Get parsha information
print("\n📖 Parsha Analysis:")
parsha = get_parsha_from_hebcal(TARGET_DATE)
print(f"  get_parsha_from_hebcal({TARGET_DATE}): {parsha}")

# Also check via jewcal_times_for_sequence
print("\n⏰ jewcal_times_for_sequence() Analysis (Jerusalem):")
# Jerusalem coordinates
lat, lon = 31.779737, 35.209554
info = jewcal_times_for_sequence(lat, lon, seq_start, seq_end, 40)
print(f"  parsha: {info.get('parsha')}")
print(f"  event_name: {info.get('event_name')}")
print(f"  event_type: {info.get('event_type')}")
print(f"  candle: {info.get('candle')}")
print(f"  havdalah: {info.get('havdalah')}")

# Step 4: Calculate is_shabbat_chol_hamoed using the EXACT logic from make_shabbat_posts.py
print("\n🎯 is_shabbat_chol_hamoed Calculation:")
# The logic from make_shabbat_posts.py lines 366-370:
# is_shabbat_chol_hamoed = (
#     event_type == "yomtov" and
#     seq_end and seq_end.weekday() == 5 and  # Saturday
#     not parsha  # No parsha during Chol HaMoed
# )
parsha_from_sequence = info.get("parsha")
is_shabbat_chol_hamoed = (
    event_type == "yomtov" and
    seq_end and seq_end.weekday() == 5 and  # Saturday
    not parsha_from_sequence  # No parsha during Chol HaMoed
)

print(f"  event_type == 'yomtov': {event_type == 'yomtov'} ({event_type})")
print(f"  seq_end exists: {seq_end is not None}")
print(f"  seq_end.weekday() == 5: {seq_end.weekday() == 5} (actual: {seq_end.weekday()})")
print(f"  not parsha: {not parsha_from_sequence} (parsha={parsha_from_sequence!r})")
print(f"  ➡️ is_shabbat_chol_hamoed: {is_shabbat_chol_hamoed}")

# Step 5: Show what the title would be
print("\n📋 Expected Title Logic:")
if is_shabbat_chol_hamoed:
    print("  Title would be: 'שבת שלום' (Shabbat Chol HaMoed)")
elif event_type == "yomtov":
    if "Pesach" in (event_name or ""):
        print("  Title would be: 'חג כשר ושמח' (Pesach)")
    else:
        print(f"  Title would be: 'חג שמח' (Yom Tov - {event_name})")
else:
    print("  Title would be: 'שבת שלום' (Regular Shabbat)")

# Step 6: Check the days around 2026-04-04
print("\n📆 Context - Days around the target date:")
for offset in range(-2, 5):
    check_date = TARGET_DATE + timedelta(days=offset)
    jc = JewCal(gregorian_date=check_date, diaspora=False)
    marker = ">>> " if offset == 0 else "    "
    events_str = ""
    if jc.has_events():
        if jc.events.yomtov:
            events_str = f"yomtov={jc.events.yomtov}"
        elif jc.events.shabbos:
            events_str = f"shabbos={jc.events.shabbos}"
        events_str += f", action={jc.events.action}"
    print(f"{marker}{check_date} ({weekday_names[check_date.weekday()][:3]}) - {events_str or 'no events'}")

print("\n" + "=" * 60)
print("Analysis Complete")
print("=" * 60)

