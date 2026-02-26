"""
Shared translation dictionaries for Hebrew/English conversions.

This module provides centralized translation dictionaries for:
- Yom Tov (Jewish holidays)
- Parasha (Torah portions)
- Hebrew months

All translation data is consolidated here to avoid duplication across the codebase.
"""

from typing import Dict

# ========= YOM TOV TRANSLATIONS =========
# Merged from make_shabbat_posts.py, service.py, and api/upcoming-events.py
# Note: Numbered variations (e.g., "Pesach 1") are handled by prefix matching in translate_yomtov()
YOMTOV_TRANSLATIONS: Dict[str, str] = {
    # Rosh Hashana
    "Erev Rosh Hashana": "ערב ראש השנה",
    "Rosh Hashana": "ראש השנה",
    "Rosh Hashanah": "ראש השנה",

    # Yom Kippur
    "Erev Yom Kippur": "ערב יום כיפור",
    "Yom Kippur": "יום כיפור",

    # Sukkot
    "Erev Sukkos": "ערב סוכות",
    "Erev Sukkot": "ערב סוכות",
    "Sukkot": "סוכות",
    "Sukkos": "סוכות",
    "Hoshana Rabba": "הושענא רבה",
    "Shmini Atzeres": "שמיני עצרת",
    "Shmini Atzeret": "שמיני עצרת",
    "Shemini Atzeret": "שמיני עצרת",
    "Simchas Tora": "שמחת תורה",
    "Simchat Tora": "שמחת תורה",
    "Simchas Torah": "שמחת תורה",
    "Simchat Torah": "שמחת תורה",
    "Shmini Atzeret / Simchat Tora": "שמיני עצרת / שמחת תורה",

    # Pesach
    "Erev Pesach": "ערב פסח",
    "Pesach": "פסח",
    "Passover": "פסח",

    # Shavuos
    "Erev Shavuos": "ערב שבועות",
    "Erev Shavut": "ערב שבועות",
    "Shavuos": "שבועות",
    "Shavut": "שבועות",
    "Shavuot": "שבועות",

    # Chol HaMoed
    "Chol HaMoed": "חול המועד",

    # Other holidays
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
}


def translate_yomtov(event_name: str) -> str:
    """
    Translate a Yom Tov (Jewish holiday) name from English to Hebrew.

    Tries exact match first, then prefix matching for variations like
    "Pesach I", "Sukkot II", etc.

    Args:
        event_name: The English name of the holiday

    Returns:
        The Hebrew translation if found, otherwise the original event_name
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


# ========= FULL PARASHA TRANSLATION =========
PARASHA_TRANSLATION: Dict[str, str] = {
    # ספר בראשית
    "Bereshit": "בראשית", "Noach": "נח", "Lech-Lecha": "לך לך", "Vayera": "וירא",
    "Chayei Sara": "חיי שרה", "Toldot": "תולדות", "Vayetzei": "ויצא",
    "Vayishlach": "וישלח", "Vayeshev": "וישב", "Miketz": "מקץ", "Vayigash": "ויגש",
    "Vayechi": "ויחי",

    # ספר שמות
    "Shemot": "שמות", "Vaera": "וארא", "Bo": "בא",
    "Beshalach": "בשלח", "Yitro": "יתרו", "Mishpatim": "משפטים", "Terumah": "תרומה",
    "Tetzaveh": "תצוה", "Ki Tisa": "כי תשא", "Vayakhel": "ויקהל", "Pekudei": "פקודי",

    # ספר ויקרא
    "Vayikra": "ויקרא", "Tzav": "צו", "Shemini": "שמיני", "Shmini": "שמיני", "Tazria": "תזריע",
    "Metzora": "מצורע", "Achrei Mot": "אחרי מות", "Kedoshim": "קדושים",
    "Emor": "אמור", "Behar": "בהר", "Bechukotai": "בחוקותי",

    # ספר במדבר
    "Bamidbar": "במדבר", "Nasso": "נשא", "Beha'alotcha": "בהעלותך", "Shelach": "שלח",
    "Korach": "קרח", "Chukat": "חוקת", "Balak": "בלק", "Pinchas": "פנחס",
    "Matot": "מטות", "Masei": "מסעי",

    # ספר דברים
    "Devarim": "דברים", "Vaetchanan": "ואתחנן", "Ekev": "עקב",
    "Re'eh": "ראה", "Shoftim": "שופטים", "Ki Tetzei": "כי תצא", "Ki Tavo": "כי תבוא",
    "Nitzavim": "נצבים", "Vayelech": "וילך", "Ha'Azinu": "האזינו",
    "Vezot Haberakhah": "וזאת הברכה",

    # וריאציות נוספות שעלולות להופיע ב-API
    "Lech Lecha": "לך לך", "Chayei Sarah": "חיי שרה", "Vayeitzei": "ויצא",
    "Ki Sisa": "כי תשא", "Acharei Mot": "אחרי מות", "Bechukosai": "בחוקותי",
    "Beha'aloscha": "בהעלותך", "Shlach": "שלח", "Chukas": "חוקת",
    "Matos": "מטות", "Mas'ei": "מסעי", "Va'eschanan": "ואתחנן",
    "Re'e": "ראה", "Ki Seitzei": "כי תצא", "Ki Savo": "כי תבוא",
    "Vayeilech": "וילך", "Haazinu": "האזינו", "Ha'azinu": "האזינו", "Ha'Azinu": "האזינו",
    "V'Zot HaBerachah": "וזאת הברכה", "Vzot Haberachah": "וזאת הברכה",
    # וריאציות נוספות מ-Hebcal API
    "Eikev": "עקב", "Ki Teitzei": "כי תצא", "Ki Tetze": "כי תצא",

    # פרשות מחוברות (כשקוראים שתי פרשות באותה שבת)
    "Vayakhel-Pekudei": "ויקהל-פקודי", "Vayakhel-Pekudey": "ויקהל-פקודי",
    "Tazria-Metzora": "תזריע-מצורע", "Tazria-Metsora": "תזריע-מצורע",
    "Achrei Mot-Kedoshim": "אחרי מות-קדושים", "Acharei Mot-Kedoshim": "אחרי מות-קדושים",
    "Behar-Bechukotai": "בהר-בחוקותי", "Behar-Bechukosai": "בהר-בחוקותי",
    "Chukat-Balak": "חוקת-בלק", "Chukas-Balak": "חוקת-בלק",
    "Matot-Masei": "מטות-מסעי", "Matos-Masei": "מטות-מסעי", "Matot-Mas'ei": "מטות-מסעי",
    "Nitzavim-Vayelech": "נצבים-וילך", "Nitzavim-Vayeilech": "נצבים-וילך",
}


def _normalize_parsha_key(name: str) -> str:
    """Normalize a parsha name for lookup (lowercase, remove apostrophes and hyphens)."""
    return name.lower().replace("'", "").replace("-", "").replace(" ", "")


# Build normalized lookup tables at module load time for O(1) lookup
_PARASHA_EXACT_LOOKUP: Dict[str, str] = {k.lower(): v for k, v in PARASHA_TRANSLATION.items()}
_PARASHA_NORMALIZED_LOOKUP: Dict[str, str] = {
    _normalize_parsha_key(k): v for k, v in PARASHA_TRANSLATION.items()
}


# ========= HEBREW MONTH TRANSLATION =========
HEBREW_MONTH_NAMES: Dict[str, str] = {
    "Nisan": "ניסן",
    "Iyar": "אייר",
    "Sivan": "סיון",
    "Tammuz": "תמוז",
    "Av": "אב",
    "Elul": "אלול",
    "Tishrei": "תשרי",
    "Cheshvan": "חשון",
    "Kislev": "כסלו",
    "Teves": "טבת",
    "Tevet": "טבת",
    "Shevat": "שבט",
    "Adar": "אדר",
    "Adar I": "אדר א'",
    "Adar II": "אדר ב'",
}

