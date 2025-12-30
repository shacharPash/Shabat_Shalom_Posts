"""
Vercel serverless function for getting upcoming Shabbat/holiday events.
"""

import json
import os
import sys
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler

# Add parent directory to path for Vercel serverless environment
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from make_shabbat_posts import find_next_sequence, get_parsha_from_hebcal


# Yom Tov name translations
YOMTOV_TRANSLATIONS = {
    "Rosh Hashana": "ראש השנה",
    "Rosh Hashanah": "ראש השנה",
    "Yom Kippur": "יום כיפור",
    "Sukkos": "סוכות",
    "Sukkot": "סוכות",
    "Shmini Atzeres": "שמיני עצרת",
    "Shemini Atzeret": "שמיני עצרת",
    "Simchas Torah": "שמחת תורה",
    "Simchat Torah": "שמחת תורה",
    "Pesach": "פסח",
    "Passover": "פסח",
    "Shavuos": "שבועות",
    "Shavuot": "שבועות",
    "Chanukah": "חנוכה",
    "Hanukkah": "חנוכה",
    "Purim": "פורים",
    "Tu BiShvat": "ט״ו בשבט",
    "Tu B'Shvat": "ט״ו בשבט",
    "Lag BaOmer": "ל״ג בעומר",
    "Lag B'Omer": "ל״ג בעומר",
    "Tisha B'Av": "תשעה באב",
    "Yom HaShoah": "יום השואה",
    "Yom HaZikaron": "יום הזיכרון",
    "Yom HaAtzmaut": "יום העצמאות",
    "Yom Yerushalayim": "יום ירושלים",
    "Chol HaMoed": "חול המועד",
    "Shmini Atzeret": "שמיני עצרת",
    "Simchat Tora": "שמחת תורה",
    "Shmini Atzeret / Simchat Tora": "שמיני עצרת / שמחת תורה",
}


def get_upcoming_events():
    """Get upcoming Shabbat/holiday events for one year ahead."""
    events = []
    current_date = date.today()
    # Calculate end date as one year from today
    one_year_ahead = date(current_date.year + 1, current_date.month, current_date.day)

    i = 0
    while current_date < one_year_ahead:
        seq_start, seq_end, event_type, event_name = find_next_sequence(current_date)

        # Get parsha for Shabbat
        parsha = None
        if event_type == "shabbos" or seq_end.weekday() == 5:  # Saturday
            parsha = get_parsha_from_hebcal(seq_end)

        # Format event name in Hebrew
        if event_type == "shabbos":
            display_name = parsha if parsha else "שבת"
        else:
            # Try exact match first, then try partial match
            display_name = YOMTOV_TRANSLATIONS.get(event_name)
            if not display_name:
                # Try matching prefix (for "Pesach I", "Sukkot II", etc.)
                for eng, heb in YOMTOV_TRANSLATIONS.items():
                    if event_name.startswith(eng):
                        display_name = heb
                        break
                else:
                    display_name = event_name

            # For Chol HaMoed on Shabbat (Saturday), show "שבת חול המועד"
            is_shabbat = seq_end.weekday() == 5  # Saturday
            if "Chol HaMoed" in event_name and is_shabbat:
                display_name = "שבת חול המועד"

        # Format date in Hebrew style
        date_str = f"{seq_start.day}/{seq_start.month}"
        if seq_start != seq_end:
            date_str += f" - {seq_end.day}/{seq_end.month}"

        events.append({
            "startDate": seq_start.isoformat(),
            "endDate": seq_end.isoformat(),
            "eventType": event_type,
            "eventName": event_name,
            "displayName": display_name,
            "parsha": parsha,  # Include parsha separately for search
            "dateStr": date_str,
            "isNext": i == 0,
        })

        # Move to day after this sequence ends
        current_date = seq_end + timedelta(days=1)
        i += 1

    return events


class handler(BaseHTTPRequestHandler):
    """Vercel serverless function entrypoint for upcoming events."""

    def do_GET(self):
        try:
            events = get_upcoming_events()

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "public, max-age=3600")  # Cache for 1 hour
            self.end_headers()
            self.wfile.write(json.dumps(events, ensure_ascii=False).encode("utf-8"))

        except Exception as e:
            error_msg = json.dumps({"error": str(e)}, ensure_ascii=False).encode("utf-8")
            self.send_response(500)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(error_msg)

