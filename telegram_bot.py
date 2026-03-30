"""
Telegram bot module for Shabbat poster generation.

Handles all bot commands and photo processing for generating personalized
Shabbat time posters via Telegram.
"""

import base64
import io
import os
import re
from typing import Any, Dict, List, Optional

import requests

from redis_client import get_redis_client, get_user_prefs, set_user_prefs, DEFAULT_PREFERENCES
from api.poster import build_poster_from_payload
from cities import build_city_lookup, get_cities_list, SPECIAL_OFFSET_CITIES, DEFAULT_CANDLE_OFFSET

# Load city lookup and list once at module level
AVAILABLE_CITIES = get_cities_list()
CITY_BY_NAME = build_city_lookup(AVAILABLE_CITIES)

# Bot token from environment
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# State key pattern for conversation flow
USER_STATE_KEY = "zmunah:state:{user_id}"

# Website URL for web version
WEB_APP_URL = os.getenv("WEB_APP_URL", "https://shabat-posts.vercel.app/")

# Date format display names
DATE_FORMAT_LABELS = {
    "hebrew": "עברי",
    "gregorian": "לועזי",
    "both": "שניהם",
}


def get_user_id(update: Dict[str, Any]) -> Optional[str]:
    """Extract user ID from a Telegram update."""
    message = update.get("message") or update.get("callback_query", {}).get("message")
    if message:
        user = message.get("from") or update.get("callback_query", {}).get("from")
        if user:
            return str(user.get("id"))
    return None


def get_chat_id(update: Dict[str, Any]) -> Optional[int]:
    """Extract chat ID from a Telegram update."""
    message = update.get("message") or update.get("callback_query", {}).get("message")
    if message:
        return message.get("chat", {}).get("id")
    return None


def send_message(chat_id: int, text: str, parse_mode: str = "HTML") -> Dict[str, Any]:
    """Send a text message to a Telegram chat."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
    }
    response = requests.post(url, json=payload, timeout=30)
    return response.json()


def send_photo(chat_id: int, photo_bytes: bytes, caption: str = "") -> Dict[str, Any]:
    """Send a photo to a Telegram chat."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    files = {"photo": ("poster.png", photo_bytes, "image/png")}
    data = {"chat_id": chat_id}
    if caption:
        data["caption"] = caption
    response = requests.post(url, data=data, files=files, timeout=60)
    return response.json()


def download_photo(file_id: str) -> Optional[bytes]:
    """Download a photo from Telegram by file ID."""
    # Get file path
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getFile"
    response = requests.get(url, params={"file_id": file_id}, timeout=30)
    result = response.json()
    
    if not result.get("ok"):
        return None
    
    file_path = result.get("result", {}).get("file_path")
    if not file_path:
        return None
    
    # Download file
    download_url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}"
    response = requests.get(download_url, timeout=60)
    if response.status_code == 200:
        return response.content
    return None


# --- Inline Keyboard Functions ---


def send_message_with_keyboard(
    chat_id: int, text: str, keyboard: List[List[Dict[str, str]]], parse_mode: str = None
) -> Dict[str, Any]:
    """Send message with inline keyboard."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "reply_markup": {"inline_keyboard": keyboard},
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode
    response = requests.post(url, json=payload, timeout=30)
    return response.json()


def answer_callback_query(callback_id: str, text: str = None) -> Dict[str, Any]:
    """Answer callback query to remove loading state."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery"
    payload = {"callback_query_id": callback_id}
    if text:
        payload["text"] = text
    response = requests.post(url, json=payload, timeout=30)
    return response.json()


def edit_message_with_keyboard(
    chat_id: int,
    message_id: int,
    text: str,
    keyboard: List[List[Dict[str, str]]],
    parse_mode: str = None,
) -> Dict[str, Any]:
    """Edit message with new text and keyboard."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/editMessageText"
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "reply_markup": {"inline_keyboard": keyboard},
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode
    response = requests.post(url, json=payload, timeout=30)
    return response.json()


def edit_message_keyboard_only(
    chat_id: int, message_id: int, keyboard: List[List[Dict[str, str]]]
) -> Dict[str, Any]:
    """Edit only the keyboard of a message (keeps text unchanged)."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/editMessageReplyMarkup"
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "reply_markup": {"inline_keyboard": keyboard},
    }
    response = requests.post(url, json=payload, timeout=30)
    return response.json()


# --- User State Management ---


def _get_user_state(user_id: str) -> Optional[str]:
    """Get user's current conversation state from Redis."""
    client = get_redis_client()
    key = USER_STATE_KEY.format(user_id=user_id)
    return client.get(key)


def _set_user_state(user_id: str, state: Optional[str]) -> None:
    """Set user's conversation state in Redis. None clears the state."""
    client = get_redis_client()
    key = USER_STATE_KEY.format(user_id=user_id)
    if state is None:
        client.delete(key)
    else:
        client.set(key, state, ex=3600)  # Expire after 1 hour


def _clear_user_state(user_id: str) -> None:
    """Clear user's conversation state."""
    _set_user_state(user_id, None)


# --- Keyboard Builders ---


def _build_settings_keyboard(poster_mode: str = "shabbat", has_saved_image: bool = False, reminder_enabled: bool = False, nusach: str = "sefard") -> List[List[Dict[str, str]]]:
    """Build the main settings inline keyboard."""
    # Toggle button text based on current mode
    if poster_mode == "omer":
        mode_button = {"text": "🔢 מצב עומר ✓", "callback_data": "toggle:mode"}
    else:
        mode_button = {"text": "🕯️ מצב שבת ✓", "callback_data": "toggle:mode"}

    # Reminder toggle button
    if reminder_enabled:
        reminder_button = {"text": "🔔 תזכורת יומית ✓", "callback_data": "toggle:reminder"}
    else:
        reminder_button = {"text": "🔕 תזכורת יומית", "callback_data": "toggle:reminder"}

    # Nusach display for button
    nusach_display = {
        "sefard": "ספרד",
        "ashkenaz": "אשכנז",
        "edot_hamizrach": "ע״מ"
    }.get(nusach, "ספרד")

    keyboard = [
        [mode_button],
        [reminder_button],
        [{"text": f"📖 נוסח: {nusach_display}", "callback_data": "edit:nusach"}],
        [{"text": "🏙️ ערוך ערים", "callback_data": "edit:cities"}],
        [{"text": "📅 פורמט תאריך", "callback_data": "edit:date"}],
        [
            {"text": "💬 ערוך ברכה", "callback_data": "edit:blessing"},
            {"text": "🕯️ לעילוי נשמת", "callback_data": "edit:dedication"},
        ],
        [{"text": "👁️ הצג דוגמה", "callback_data": "show:preview"}],
    ]

    # Add delete saved image button if there's a saved image
    if has_saved_image:
        keyboard.append([{"text": "🗑️ מחק תמונה שמורה", "callback_data": "clear:image"}])

    return keyboard


def _build_help_keyboard() -> List[List[Dict[str, str]]]:
    """Build help keyboard for unrecognized messages."""
    return [
        [
            {"text": "⚙️ הגדרות", "callback_data": "start:settings"},
            {"text": "📸 צור פוסטר", "callback_data": "start:poster"},
        ],
        [{"text": "💻 לאתר", "url": WEB_APP_URL}],
    ]



CITIES_PER_PAGE = 12


def _build_cities_keyboard(
    selected_cities: List[Dict[str, Any]], page: int = 0
) -> List[List[Dict[str, str]]]:
    """Build city selection grid with toggles and pagination.

    Selected cities appear first on page 0, then unselected cities continue.
    """
    selected_names = {
        c.get("name", c) if isinstance(c, dict) else c for c in selected_cities
    }

    # Separate selected and unselected cities
    selected_list = [c for c in AVAILABLE_CITIES if c["name"] in selected_names]
    unselected_list = [c for c in AVAILABLE_CITIES if c["name"] not in selected_names]

    # Combined list: selected first, then unselected (maintains population sort within each group)
    combined_cities = selected_list + unselected_list
    total_cities = len(combined_cities)
    total_pages = (total_cities + CITIES_PER_PAGE - 1) // CITIES_PER_PAGE
    page = max(0, min(page, total_pages - 1))  # Clamp to valid range

    start = page * CITIES_PER_PAGE
    end = min(start + CITIES_PER_PAGE, total_cities)

    buttons = []
    row = []
    for city in combined_cities[start:end]:
        name = city["name"]
        prefix = "✓ " if name in selected_names else ""
        row.append({"text": f"{prefix}{name}", "callback_data": f"city:{name}:{page}"})
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    # Navigation row
    nav_row = []
    if page > 0:
        nav_row.append({"text": "← הקודם", "callback_data": f"cities:page:{page - 1}"})
    nav_row.append({"text": f"עמוד {page + 1}/{total_pages}", "callback_data": "cities:noop"})
    if page < total_pages - 1:
        nav_row.append({"text": "הבא →", "callback_data": f"cities:page:{page + 1}"})
    buttons.append(nav_row)

    # Search and done buttons
    buttons.append([{"text": "🔍 חפשו ערים", "callback_data": "cities:search"}])
    buttons.append([{"text": "✅ סיום", "callback_data": "cities:done"}])
    return buttons


def _build_search_results_keyboard(
    query: str, selected_cities: List[Dict[str, Any]]
) -> List[List[Dict[str, str]]]:
    """Build keyboard with search results. Supports multiple cities separated by commas."""
    selected_names = {
        c.get("name", c) if isinstance(c, dict) else c for c in selected_cities
    }

    # Split query by comma or spaces and search for each term
    search_terms = [term.strip().lower() for term in re.split(r'[,\s]+', query) if term.strip()]

    # Find matches for all search terms (union of results)
    matches = []
    seen_names = set()
    for term in search_terms:
        for city in AVAILABLE_CITIES:
            if term in city["name"].lower() and city["name"] not in seen_names:
                matches.append(city)
                seen_names.add(city["name"])

    buttons = []
    row = []
    for city in matches[:12]:  # Limit to 12 results
        name = city["name"]
        prefix = "✓ " if name in selected_names else ""
        row.append({"text": f"{prefix}{name}", "callback_data": f"city:{name}:search"})
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    if not matches:
        buttons.append([{"text": "לא נמצאו תוצאות", "callback_data": "cities:noop"}])

    buttons.append([{"text": "⬅️ חזרה לרשימה", "callback_data": "cities:cancel_search"}])
    return buttons


def _build_date_format_keyboard(current: str) -> List[List[Dict[str, str]]]:
    """Build date format selection keyboard."""
    buttons = []
    for fmt, label in DATE_FORMAT_LABELS.items():
        prefix = "✓ " if fmt == current else ""
        buttons.append({"text": f"{prefix}{label}", "callback_data": f"date:{fmt}"})
    return [buttons, [{"text": "⬅️ חזרה", "callback_data": "settings:back"}]]


def format_settings(prefs: Dict[str, Any]) -> str:
    """Format user preferences as a readable message."""
    cities = prefs.get("cities", [])
    city_names = [c.get("name", "?") for c in cities] if cities else ["ברירת מחדל"]

    date_format = prefs.get("date_format", "both")
    date_format_display = {
        "gregorian": "לועזי",
        "hebrew": "עברי",
        "both": "לועזי + עברי"
    }.get(date_format, date_format)

    blessing = prefs.get("blessing_text") or "לא מוגדר"
    dedication = prefs.get("dedication_text") or "לא מוגדר"

    # Poster mode display
    poster_mode = prefs.get("poster_mode", "shabbat")
    mode_display = "🔢 ספירת העומר" if poster_mode == "omer" else "🕯️ שבת"

    # Reminder display
    reminder_enabled = prefs.get("reminder_enabled", False)
    reminder_display = "🔔 פעיל" if reminder_enabled else "🔕 כבוי"

    # Nusach display
    nusach = prefs.get("nusach", "sefard")
    nusach_display = {
        "sefard": "ספרד",
        "ashkenaz": "אשכנז",
        "edot_hamizrach": "עדות המזרח"
    }.get(nusach, "ספרד")

    return (
        "⚙️ <b>ההגדרות שלך:</b>\n\n"
        f"📋 <b>מצב:</b> {mode_display}\n"
        f"⏰ <b>תזכורת יומית:</b> {reminder_display}\n"
        f"📖 <b>נוסח:</b> {nusach_display}\n"
        f"🏙 <b>ערים:</b> {', '.join(city_names)}\n"
        f"📅 <b>פורמט תאריך:</b> {date_format_display}\n"
        f"✨ <b>ברכה:</b> {blessing}\n"
        f"🕯 <b>לעילוי נשמת:</b> {dedication}\n\n"
        "לשינוי הגדרות, השתמש בכפתורים למטה."
    )


def handle_start(update: Dict[str, Any]) -> None:
    """Handle /start command."""
    chat_id = get_chat_id(update)
    if not chat_id:
        return

    welcome_text = (
        "🕯️ <b>שלום וברוכים הבאים!</b>\n\n"
        "אני בוט שיעזור לך ליצור פוסטרים יפים לשבת ולספירת העומר.\n\n"
        "<b>🎨 שני מצבים:</b>\n"
        "• <b>שבת</b> - פוסטר עם זמני שבת ופרשת השבוע\n"
        "• <b>ספירת העומר</b> - פוסטר עם ספירת העומר והברכה\n\n"
        "<b>איך להשתמש:</b>\n"
        "1️⃣ שלח לי תמונה\n"
        "2️⃣ אני אצור פוסטר מעוצב\n"
        "3️⃣ קבל פוסטר מוכן לשיתוף!\n\n"
        "🔔 <b>תזכורות יומיות:</b>\n"
        "הפעל תזכורת וקבל פוסטר ספירת העומר כל יום אחרי צאת הכוכבים!\n"
        "להפעלה: /reminder או דרך ההגדרות\n\n"
        "<b>פקודות:</b>\n"
        "/poster - צור פוסטר (לפי המצב הנבחר)\n"
        "/omer - צור פוסטר ספירת העומר\n"
        "/reminder - הפעל/כבה תזכורת יומית\n"
        "/settings - הגדרות ובחירת מצב\n\n"
        "שלח תמונה כדי להתחיל! 📸"
    )
    keyboard = [
        [{"text": "📸 צור פוסטר עכשיו", "callback_data": "start:poster"}],
        [
            {"text": "⚙️ הגדרות", "callback_data": "start:settings"},
            {"text": "🔔 תזכורות", "callback_data": "toggle:reminder"},
        ]
    ]
    send_message_with_keyboard(chat_id, welcome_text, keyboard, parse_mode="HTML")


def handle_settings(update: Dict[str, Any]) -> None:
    """Handle /settings command - show settings with inline keyboard."""
    chat_id = get_chat_id(update)
    user_id = get_user_id(update)
    if not chat_id or not user_id:
        return

    prefs = get_user_prefs(user_id)

    # Show settings menu (preview is now shown on-demand via button)
    settings_text = format_settings(prefs)
    has_saved_image = bool(prefs.get("last_image_file_id"))
    reminder_enabled = prefs.get("reminder_enabled", False)
    nusach = prefs.get("nusach", "sefard")
    keyboard = _build_settings_keyboard(prefs.get("poster_mode", "shabbat"), has_saved_image, reminder_enabled, nusach)
    send_message_with_keyboard(chat_id, settings_text, keyboard, parse_mode="HTML")


def handle_reset(update: Dict[str, Any]) -> None:
    """Handle /reset command - reset to default settings."""
    chat_id = get_chat_id(update)
    user_id = get_user_id(update)
    if not chat_id or not user_id:
        return

    set_user_prefs(user_id, DEFAULT_PREFERENCES.copy())
    send_message(chat_id, "✅ ההגדרות אופסו לברירת מחדל.")


def handle_skip(update: Dict[str, Any]) -> None:
    """Handle /skip command - cancel text editing or city search."""
    chat_id = get_chat_id(update)
    user_id = get_user_id(update)
    if not chat_id or not user_id:
        return

    state = _get_user_state(user_id)
    if state and state.startswith("editing_"):
        _clear_user_state(user_id)
        send_message(chat_id, "⏭️ דילגת על העריכה")
        # Show settings
        prefs = get_user_prefs(user_id)
        settings_text = format_settings(prefs)
        has_saved_image = bool(prefs.get("last_image_file_id"))
        reminder_enabled = prefs.get("reminder_enabled", False)
        nusach = prefs.get("nusach", "sefard")
        keyboard = _build_settings_keyboard(prefs.get("poster_mode", "shabbat"), has_saved_image, reminder_enabled, nusach)
        send_message_with_keyboard(chat_id, settings_text, keyboard, parse_mode="HTML")
    elif state in ("searching_city",) or (state and state.startswith("search_results:")):
        _clear_user_state(user_id)
        send_message(chat_id, "⏭️ ביטלת את החיפוש")
        # Show city selection
        prefs = get_user_prefs(user_id)
        keyboard = _build_cities_keyboard(prefs.get("cities", []))
        send_message_with_keyboard(
            chat_id, "🏙️ בחר ערים (לחץ להוספה/הסרה):", keyboard
        )
    else:
        send_message(chat_id, "אין מה לדלג - אתה לא במצב עריכה")


def handle_clear_blessing(update: Dict[str, Any]) -> None:
    """Handle /clear_blessing command - clear blessing text."""
    chat_id = get_chat_id(update)
    user_id = get_user_id(update)
    if not chat_id or not user_id:
        return

    prefs = get_user_prefs(user_id)
    prefs["blessing_text"] = None
    set_user_prefs(user_id, prefs)
    _clear_user_state(user_id)  # Clear any editing state
    send_message(chat_id, "✅ הברכה נמחקה")


def handle_clear_dedication(update: Dict[str, Any]) -> None:
    """Handle /clear_dedication command - clear dedication text."""
    chat_id = get_chat_id(update)
    user_id = get_user_id(update)
    if not chat_id or not user_id:
        return

    prefs = get_user_prefs(user_id)
    prefs["dedication_text"] = None
    set_user_prefs(user_id, prefs)
    _clear_user_state(user_id)  # Clear any editing state
    send_message(chat_id, "✅ לעילוי נשמת נמחק")


def handle_clear_image(update: Dict[str, Any]) -> None:
    """Handle /clear_image command - clear saved image."""
    chat_id = get_chat_id(update)
    user_id = get_user_id(update)
    if not chat_id or not user_id:
        return

    prefs = get_user_prefs(user_id)
    if prefs.get("last_image_file_id"):
        prefs["last_image_file_id"] = None
        set_user_prefs(user_id, prefs)
        send_message(chat_id, "✅ התמונה השמורה נמחקה")
    else:
        send_message(chat_id, "ℹ️ אין תמונה שמורה למחיקה")


def handle_help(update: Dict[str, Any]) -> None:
    """Handle /help command - show available commands."""
    chat_id = get_chat_id(update)
    if not chat_id:
        return

    help_text = (
        "📋 <b>פקודות זמינות:</b>\n\n"
        "/start - התחל מחדש\n"
        "/poster - 📸 צור פוסטר (שבת/עומר לפי ההגדרות)\n"
        "/omer - 🔢 צור פוסטר ספירת העומר\n"
        "/reminder - 🔔 הפעל/כבה תזכורת יומית\n"
        "/settings - ⚙️ הגדרות\n"
        "/reset - 🔄 איפוס להגדרות ברירת מחדל\n"
        "/clear_blessing - נקה טקסט ברכה\n"
        "/clear_memorial - נקה לעילוי נשמת\n"
        "/clear_image - 🗑️ מחק תמונה שמורה\n\n"
        "💡 <b>שימוש:</b>\n"
        "שלח תמונה ואני אצור ממנה פוסטר!"
    )
    send_message(chat_id, help_text)


def handle_reminder(update: Dict[str, Any]) -> None:
    """Handle /reminder command - toggle or set Omer reminder.

    Usage:
    - /reminder on - Enable daily Omer reminder
    - /reminder off - Disable daily Omer reminder
    - /reminder (no args) - Toggle current state
    """
    chat_id = get_chat_id(update)
    user_id = get_user_id(update)
    if not chat_id or not user_id:
        return

    message = update.get("message", {})
    text = message.get("text", "").strip()

    # Parse argument
    parts = text.split()
    arg = parts[1].lower() if len(parts) > 1 else None

    prefs = get_user_prefs(user_id)
    current_state = prefs.get("reminder_enabled", False)

    if arg == "on":
        new_state = True
    elif arg == "off":
        new_state = False
    else:
        # Toggle
        new_state = not current_state

    prefs["reminder_enabled"] = new_state
    set_user_prefs(user_id, prefs)

    if new_state:
        send_message(
            chat_id,
            "🔔 <b>תזכורת יומית הופעלה!</b>\n\n"
            "תקבל פוסטר ספירת העומר כל יום אחרי צאת הכוכבים בתקופת העומר.\n\n"
            "לביטול: /reminder off"
        )
    else:
        send_message(
            chat_id,
            "🔕 <b>תזכורת יומית כובתה.</b>\n\n"
            "להפעלה מחדש: /reminder on"
        )


def handle_poster(update: Dict[str, Any], force_omer: bool = False) -> None:
    """Handle /poster command - generate poster with saved or default image.

    Args:
        update: Telegram update object
        force_omer: If True, force omer mode regardless of user settings
    """
    chat_id = get_chat_id(update)
    user_id = get_user_id(update)
    if not chat_id or not user_id:
        return

    # Notify user we're working
    send_message(chat_id, "⏳ יוצר את הפוסטר שלך...")

    try:
        # Get user preferences
        prefs = get_user_prefs(user_id)

        # Determine if omer mode should be used
        use_omer_mode = force_omer or prefs.get("poster_mode") == "omer"

        # Build payload for poster generation
        payload = {
            "dateFormat": prefs.get("date_format", "both"),
        }

        # Add omer mode if enabled
        if use_omer_mode:
            payload["omerMode"] = True
            payload["nusach"] = prefs.get("nusach", "sefard")

        # Check if user has a saved image
        saved_file_id = prefs.get("last_image_file_id")
        used_saved_image = False
        if saved_file_id:
            # Download the saved image from Telegram
            photo_bytes = download_photo(saved_file_id)
            if photo_bytes:
                payload["imageBase64"] = base64.b64encode(photo_bytes).decode("utf-8")
                used_saved_image = True

        # Add cities if defined
        cities = prefs.get("cities")
        if cities:
            mapped_cities = []
            for city in cities:
                name = city.get("name") if isinstance(city, dict) else city
                offset = city.get("candle_offset", 20) if isinstance(city, dict) else 20
                if name in CITY_BY_NAME:
                    full_city = CITY_BY_NAME[name].copy()
                    full_city["candle_offset"] = offset
                    mapped_cities.append(full_city)
            if mapped_cities:
                payload["cities"] = mapped_cities

        # Add blessing text if defined
        blessing = prefs.get("blessing_text")
        if blessing:
            payload["message"] = blessing

        # Add dedication text if defined
        dedication = prefs.get("dedication_text")
        if dedication:
            payload["leiluyNeshama"] = dedication

        # Generate poster
        poster_bytes = build_poster_from_payload(payload)

        # Send poster back to user with appropriate caption
        if use_omer_mode:
            caption = "🔢 פוסטר ספירת העומר שלך מוכן!"
            if used_saved_image:
                caption += "\n📸 נוצר עם התמונה השמורה שלך."
        else:
            if used_saved_image:
                caption = "🕯️ הפוסטר שלך מוכן! שבת שלום!\n📸 נוצר עם התמונה השמורה שלך."
            else:
                caption = "🕯️ הפוסטר שלך מוכן! שבת שלום!"
        send_photo(chat_id, poster_bytes, caption)

    except Exception as e:
        send_message(chat_id, f"❌ שגיאה ביצירת הפוסטר: {str(e)}")


def handle_omer(update: Dict[str, Any]) -> None:
    """Handle /omer command - generate omer poster directly."""
    handle_poster(update, force_omer=True)


def handle_photo(update: Dict[str, Any]) -> None:
    """Handle photo message - generate poster from user photo."""
    chat_id = get_chat_id(update)
    user_id = get_user_id(update)
    if not chat_id or not user_id:
        return

    message = update.get("message", {})
    photos = message.get("photo", [])

    if not photos:
        send_message(chat_id, "❌ לא נמצאה תמונה. נסה שוב.")
        return

    # Get the largest photo (last in array)
    file_id = photos[-1].get("file_id")
    if not file_id:
        send_message(chat_id, "❌ שגיאה בקבלת התמונה. נסה שוב.")
        return

    # Notify user we're working
    send_message(chat_id, "⏳ יוצר את הפוסטר שלך...")

    try:
        # Download the photo
        photo_bytes = download_photo(file_id)
        if not photo_bytes:
            send_message(chat_id, "❌ שגיאה בהורדת התמונה. נסה שוב.")
            return

        # Get user preferences
        prefs = get_user_prefs(user_id)

        # Save the file_id for future use
        prefs["last_image_file_id"] = file_id
        set_user_prefs(user_id, prefs)

        # Determine if omer mode should be used
        use_omer_mode = prefs.get("poster_mode") == "omer"

        # Build payload for poster generation
        payload = {
            "imageBase64": base64.b64encode(photo_bytes).decode("utf-8"),
            "dateFormat": prefs.get("date_format", "both"),
        }

        # Add omer mode if enabled
        if use_omer_mode:
            payload["omerMode"] = True
            payload["nusach"] = prefs.get("nusach", "sefard")

        # Add cities if defined
        cities = prefs.get("cities")
        if cities:
            # Map city names to full city objects with coordinates
            mapped_cities = []
            for city in cities:
                name = city.get("name") if isinstance(city, dict) else city
                offset = city.get("candle_offset", 20) if isinstance(city, dict) else 20
                if name in CITY_BY_NAME:
                    full_city = CITY_BY_NAME[name].copy()
                    full_city["candle_offset"] = offset
                    mapped_cities.append(full_city)
            if mapped_cities:
                payload["cities"] = mapped_cities

        # Add blessing text if defined
        blessing = prefs.get("blessing_text")
        if blessing:
            payload["message"] = blessing

        # Add dedication text if defined
        dedication = prefs.get("dedication_text")
        if dedication:
            payload["leiluyNeshama"] = dedication

        # Generate poster
        poster_bytes = build_poster_from_payload(payload)

        # Send poster back to user with appropriate caption
        if use_omer_mode:
            caption = "🔢 פוסטר ספירת העומר שלך מוכן!\n📸 התמונה נשמרה לשימוש חוזר."
        else:
            caption = "🕯️ הפוסטר שלך מוכן! שבת שלום!\n📸 התמונה נשמרה לשימוש חוזר."
        send_photo(chat_id, poster_bytes, caption)

    except Exception as e:
        send_message(chat_id, f"❌ שגיאה ביצירת הפוסטר: {str(e)}")


# --- Callback Query Handlers ---


def handle_callback_query(update: Dict[str, Any]) -> None:
    """Route callback queries to appropriate handlers."""
    callback_query = update.get("callback_query", {})
    callback_id = callback_query.get("id")
    data = callback_query.get("data", "")

    # Always answer the callback to remove loading state
    answer_callback_query(callback_id)

    chat_id = callback_query.get("message", {}).get("chat", {}).get("id")
    message_id = callback_query.get("message", {}).get("message_id")
    user = callback_query.get("from", {})
    user_id = str(user.get("id", ""))

    if not chat_id or not user_id:
        return

    # Route based on callback data
    if data == "edit:cities":
        handle_edit_cities(chat_id, message_id, user_id)
    elif data.startswith("cities:page:"):
        page = int(data.split(":")[2])
        handle_cities_page(chat_id, message_id, user_id, page)
    elif data == "cities:search":
        handle_cities_search_start(chat_id, message_id, user_id)
    elif data == "cities:cancel_search":
        handle_cities_cancel_search(chat_id, message_id, user_id)
    elif data == "cities:noop":
        pass  # Do nothing for informational buttons
    elif data.startswith("city:"):
        parts = data.split(":")
        city_name = parts[1]
        # parts[2] is page number or "search"
        context = parts[2] if len(parts) > 2 else "0"
        handle_city_toggle(chat_id, message_id, user_id, city_name, context)
    elif data == "cities:done":
        handle_cities_done(chat_id, message_id, user_id)
    elif data == "edit:date":
        handle_edit_date(chat_id, message_id, user_id)
    elif data.startswith("date:"):
        date_format = data.split(":", 1)[1]
        handle_date_select(chat_id, message_id, user_id, date_format)
    elif data == "edit:blessing":
        handle_edit_text(chat_id, message_id, user_id, "blessing")
    elif data == "edit:dedication":
        handle_edit_text(chat_id, message_id, user_id, "dedication")
    elif data == "settings:back":
        handle_settings_back(chat_id, message_id, user_id)
    elif data == "start:settings":
        handle_start_settings(chat_id, user_id)
    elif data == "start:reset":
        handle_start_reset(chat_id, user_id)
    elif data == "start:poster":
        handle_start_poster(chat_id, user_id)
    elif data == "show:preview":
        handle_show_preview(chat_id, user_id)
    elif data == "clear:image":
        handle_clear_image_callback(chat_id, message_id, user_id)
    elif data == "toggle:mode":
        handle_toggle_mode(chat_id, message_id, user_id)
    elif data == "toggle:reminder":
        handle_toggle_reminder(chat_id, message_id, user_id)
    elif data == "edit:nusach":
        handle_edit_nusach(chat_id, message_id, user_id)
    elif data.startswith("nusach:"):
        nusach_value = data.split(":", 1)[1]
        handle_set_nusach(chat_id, message_id, user_id, nusach_value)


def handle_edit_cities(chat_id: int, message_id: int, user_id: str) -> None:
    """Show city selection grid."""
    prefs = get_user_prefs(user_id)
    keyboard = _build_cities_keyboard(prefs.get("cities", []))
    edit_message_with_keyboard(
        chat_id, message_id, "🏙️ בחר ערים (לחץ להוספה/הסרה):", keyboard
    )


def handle_cities_page(chat_id: int, message_id: int, user_id: str, page: int) -> None:
    """Show a specific page of cities."""
    prefs = get_user_prefs(user_id)
    keyboard = _build_cities_keyboard(prefs.get("cities", []), page)
    edit_message_keyboard_only(chat_id, message_id, keyboard)


def handle_cities_search_start(chat_id: int, message_id: int, user_id: str) -> None:
    """Start city search mode."""
    _set_user_state(user_id, "searching_city")
    edit_message_with_keyboard(
        chat_id,
        message_id,
        "🔍 הקלידו שמות ערים לחיפוש:\n(אפשר לכתוב מספר ערים עם פסיק או רווח, או /skip לביטול)",
        [],  # Remove keyboard
    )


def handle_cities_cancel_search(chat_id: int, message_id: int, user_id: str) -> None:
    """Cancel city search and return to city list."""
    _clear_user_state(user_id)
    prefs = get_user_prefs(user_id)
    keyboard = _build_cities_keyboard(prefs.get("cities", []))
    edit_message_with_keyboard(
        chat_id, message_id, "🏙️ בחר ערים (לחץ להוספה/הסרה):", keyboard
    )


def handle_city_toggle(
    chat_id: int, message_id: int, user_id: str, city_name: str, context: str = "0"
) -> None:
    """Toggle city selection."""
    prefs = get_user_prefs(user_id)
    current_cities = prefs.get("cities", [])
    current_names = [
        c.get("name", c) if isinstance(c, dict) else c for c in current_cities
    ]

    if city_name in current_names:
        # Remove city
        prefs["cities"] = [
            c
            for c in current_cities
            if (c.get("name", c) if isinstance(c, dict) else c) != city_name
        ]
    else:
        # Add city with appropriate offset
        offset = SPECIAL_OFFSET_CITIES.get(city_name, DEFAULT_CANDLE_OFFSET)
        prefs["cities"].append({"name": city_name, "candle_offset": offset})

    set_user_prefs(user_id, prefs)

    # Refresh keyboard based on context
    if context == "search":
        # Get the last search query from state if available
        state = _get_user_state(user_id)
        if state and state.startswith("search_results:"):
            query = state.split(":", 1)[1]
            keyboard = _build_search_results_keyboard(query, prefs.get("cities", []))
        else:
            # Fallback to city list
            keyboard = _build_cities_keyboard(prefs.get("cities", []))
    else:
        page = int(context) if context.isdigit() else 0
        keyboard = _build_cities_keyboard(prefs.get("cities", []), page)
    edit_message_keyboard_only(chat_id, message_id, keyboard)


def handle_cities_done(chat_id: int, message_id: int, user_id: str) -> None:
    """Finish city selection and return to settings."""
    handle_settings_back(chat_id, message_id, user_id)


def handle_edit_date(chat_id: int, message_id: int, user_id: str) -> None:
    """Show date format selection."""
    prefs = get_user_prefs(user_id)
    keyboard = _build_date_format_keyboard(prefs.get("date_format", "both"))
    edit_message_with_keyboard(chat_id, message_id, "📅 בחר פורמט תאריך:", keyboard)


def handle_date_select(chat_id: int, message_id: int, user_id: str, date_format: str) -> None:
    """Select date format."""
    prefs = get_user_prefs(user_id)
    prefs["date_format"] = date_format
    set_user_prefs(user_id, prefs)

    # Show updated keyboard
    keyboard = _build_date_format_keyboard(date_format)
    edit_message_keyboard_only(chat_id, message_id, keyboard)


def handle_edit_text(chat_id: int, message_id: int, user_id: str, field: str) -> None:
    """Start conversation flow for blessing/dedication text input."""
    _set_user_state(user_id, f"editing_{field}")

    field_name = "ברכה" if field == "blessing" else "לעילוי נשמת"
    clear_cmd = f"/clear_{field}"
    edit_message_with_keyboard(
        chat_id,
        message_id,
        f"📝 שלח את טקסט ה{field_name} הרצוי\n(או /skip לדלג, {clear_cmd} למחיקה)",
        [],  # Remove keyboard
    )


def handle_clear_image_callback(chat_id: int, message_id: int, user_id: str) -> None:
    """Handle clear:image callback - clear saved image and refresh settings."""
    prefs = get_user_prefs(user_id)
    prefs["last_image_file_id"] = None
    set_user_prefs(user_id, prefs)

    # Show updated settings without saved image button
    settings_text = format_settings(prefs)
    reminder_enabled = prefs.get("reminder_enabled", False)
    nusach = prefs.get("nusach", "sefard")
    keyboard = _build_settings_keyboard(prefs.get("poster_mode", "shabbat"), False, reminder_enabled, nusach)
    edit_message_with_keyboard(chat_id, message_id, settings_text + "\n\n✅ התמונה השמורה נמחקה", keyboard, parse_mode="HTML")


def handle_toggle_mode(chat_id: int, message_id: int, user_id: str) -> None:
    """Handle toggle:mode callback - toggle between shabbat and omer modes."""
    prefs = get_user_prefs(user_id)

    # Toggle the mode
    current_mode = prefs.get("poster_mode", "shabbat")
    new_mode = "shabbat" if current_mode == "omer" else "omer"
    prefs["poster_mode"] = new_mode
    set_user_prefs(user_id, prefs)

    # Refresh settings display
    settings_text = format_settings(prefs)
    has_saved_image = bool(prefs.get("last_image_file_id"))
    reminder_enabled = prefs.get("reminder_enabled", False)
    nusach = prefs.get("nusach", "sefard")
    keyboard = _build_settings_keyboard(new_mode, has_saved_image, reminder_enabled, nusach)
    edit_message_with_keyboard(chat_id, message_id, settings_text, keyboard, parse_mode="HTML")


def handle_toggle_reminder(chat_id: int, message_id: int, user_id: str) -> None:
    """Handle toggle:reminder callback - toggle Omer reminder on/off."""
    prefs = get_user_prefs(user_id)

    # Toggle the reminder
    current_state = prefs.get("reminder_enabled", False)
    new_state = not current_state
    prefs["reminder_enabled"] = new_state
    set_user_prefs(user_id, prefs)

    # Refresh settings display
    settings_text = format_settings(prefs)
    has_saved_image = bool(prefs.get("last_image_file_id"))
    nusach = prefs.get("nusach", "sefard")
    keyboard = _build_settings_keyboard(prefs.get("poster_mode", "shabbat"), has_saved_image, new_state, nusach)
    edit_message_with_keyboard(chat_id, message_id, settings_text, keyboard, parse_mode="HTML")


def handle_edit_nusach(chat_id: int, message_id: int, user_id: str) -> None:
    """Show nusach selection keyboard."""
    prefs = get_user_prefs(user_id)
    current_nusach = prefs.get("nusach", "sefard")

    # Build nusach selection keyboard with checkmark on current selection
    keyboard = [
        [
            {"text": f"{'✓ ' if current_nusach == 'sefard' else ''}ספרד", "callback_data": "nusach:sefard"},
            {"text": f"{'✓ ' if current_nusach == 'ashkenaz' else ''}אשכנז", "callback_data": "nusach:ashkenaz"},
            {"text": f"{'✓ ' if current_nusach == 'edot_hamizrach' else ''}עדות המזרח", "callback_data": "nusach:edot_hamizrach"},
        ],
        [{"text": "⬅️ חזרה", "callback_data": "settings:back"}],
    ]
    edit_message_with_keyboard(
        chat_id, message_id,
        "📖 <b>בחר נוסח לספירת העומר:</b>\n\n"
        "• <b>ספרד:</b> לָעֹמֶר\n"
        "• <b>אשכנז:</b> בָּעֹמֶר\n"
        "• <b>עדות המזרח:</b> לָעֹמֶר (מיקום שונה)",
        keyboard, parse_mode="HTML"
    )


def handle_set_nusach(chat_id: int, message_id: int, user_id: str, nusach: str) -> None:
    """Handle nusach selection."""
    if nusach not in ("sefard", "ashkenaz", "edot_hamizrach"):
        return

    prefs = get_user_prefs(user_id)
    prefs["nusach"] = nusach
    set_user_prefs(user_id, prefs)

    # Return to settings view
    settings_text = format_settings(prefs)
    has_saved_image = bool(prefs.get("last_image_file_id"))
    reminder_enabled = prefs.get("reminder_enabled", False)
    keyboard = _build_settings_keyboard(prefs.get("poster_mode", "shabbat"), has_saved_image, reminder_enabled, nusach)
    edit_message_with_keyboard(chat_id, message_id, settings_text, keyboard, parse_mode="HTML")


def handle_settings_back(chat_id: int, message_id: int, user_id: str) -> None:
    """Return to main settings view."""
    prefs = get_user_prefs(user_id)
    settings_text = format_settings(prefs)
    has_saved_image = bool(prefs.get("last_image_file_id"))
    reminder_enabled = prefs.get("reminder_enabled", False)
    nusach = prefs.get("nusach", "sefard")
    keyboard = _build_settings_keyboard(prefs.get("poster_mode", "shabbat"), has_saved_image, reminder_enabled, nusach)
    edit_message_with_keyboard(chat_id, message_id, settings_text, keyboard, parse_mode="HTML")


def handle_start_settings(chat_id: int, user_id: str) -> None:
    """Handle start:settings callback - send settings as new message."""
    prefs = get_user_prefs(user_id)
    settings_text = format_settings(prefs)
    has_saved_image = bool(prefs.get("last_image_file_id"))
    reminder_enabled = prefs.get("reminder_enabled", False)
    nusach = prefs.get("nusach", "sefard")
    keyboard = _build_settings_keyboard(prefs.get("poster_mode", "shabbat"), has_saved_image, reminder_enabled, nusach)
    send_message_with_keyboard(chat_id, settings_text, keyboard, parse_mode="HTML")


def handle_start_reset(chat_id: int, user_id: str) -> None:
    """Handle start:reset callback - reset to default settings."""
    set_user_prefs(user_id, DEFAULT_PREFERENCES.copy())
    send_message(chat_id, "✅ ההגדרות אופסו לברירת מחדל.")


def handle_start_poster(chat_id: int, user_id: str) -> None:
    """Handle start:poster callback - generate poster with default image."""
    # Notify user we're working
    send_message(chat_id, "⏳ יוצר את הפוסטר שלך...")

    try:
        # Get user preferences
        prefs = get_user_prefs(user_id)

        # Determine if omer mode should be used
        use_omer_mode = prefs.get("poster_mode") == "omer"

        # Build payload for poster generation (no image = uses default)
        payload = {
            "dateFormat": prefs.get("date_format", "both"),
        }

        # Add omer mode if enabled
        if use_omer_mode:
            payload["omerMode"] = True
            payload["nusach"] = prefs.get("nusach", "sefard")

        # Add cities if defined
        cities = prefs.get("cities")
        if cities:
            mapped_cities = []
            for city in cities:
                name = city.get("name") if isinstance(city, dict) else city
                offset = city.get("candle_offset", 20) if isinstance(city, dict) else 20
                if name in CITY_BY_NAME:
                    full_city = CITY_BY_NAME[name].copy()
                    full_city["candle_offset"] = offset
                    mapped_cities.append(full_city)
            if mapped_cities:
                payload["cities"] = mapped_cities

        # Add blessing text if defined
        blessing = prefs.get("blessing_text")
        if blessing:
            payload["message"] = blessing

        # Add dedication text if defined
        dedication = prefs.get("dedication_text")
        if dedication:
            payload["leiluyNeshama"] = dedication

        # Generate poster with default image
        poster_bytes = build_poster_from_payload(payload)

        # Send poster back to user with appropriate caption
        if use_omer_mode:
            caption = "🔢 פוסטר ספירת העומר שלך מוכן!"
        else:
            caption = "🕯️ הפוסטר שלך מוכן! שבת שלום!"
        send_photo(chat_id, poster_bytes, caption)

    except Exception as e:
        send_message(chat_id, f"❌ שגיאה ביצירת הפוסטר: {str(e)}")


def handle_show_preview(chat_id: int, user_id: str) -> None:
    """Handle show:preview callback - show preview poster with current settings."""
    try:
        prefs = get_user_prefs(user_id)

        # Determine if omer mode should be used
        use_omer_mode = prefs.get("poster_mode") == "omer"

        preview_payload = {
            "dateFormat": prefs.get("date_format", "both"),
        }

        # Add omer mode if enabled
        if use_omer_mode:
            preview_payload["omerMode"] = True

        # Add cities if defined
        cities = prefs.get("cities")
        if cities:
            mapped_cities = []
            for city in cities:
                name = city.get("name") if isinstance(city, dict) else city
                offset = city.get("candle_offset", 20) if isinstance(city, dict) else 20
                if name in CITY_BY_NAME:
                    full_city = CITY_BY_NAME[name].copy()
                    full_city["candle_offset"] = offset
                    mapped_cities.append(full_city)
            if mapped_cities:
                preview_payload["cities"] = mapped_cities

        # Add blessing text if defined
        blessing = prefs.get("blessing_text")
        if blessing:
            preview_payload["message"] = blessing

        # Add dedication text if defined
        dedication = prefs.get("dedication_text")
        if dedication:
            preview_payload["leiluyNeshama"] = dedication

        # Generate and send preview poster
        poster_bytes = build_poster_from_payload(preview_payload)
        if use_omer_mode:
            caption = "👆 כך ייראה פוסטר העומר שלך עם ההגדרות הנוכחיות"
        else:
            caption = "👆 כך ייראה הפוסטר שלך עם ההגדרות הנוכחיות"
        send_photo(chat_id, poster_bytes, caption)
    except Exception as e:
        send_message(chat_id, f"❌ שגיאה ביצירת הדוגמה: {str(e)}")


def handle_text_message(update: Dict[str, Any]) -> None:
    """Handle text messages - check if user is in editing or searching state, or show help."""
    chat_id = get_chat_id(update)
    user_id = get_user_id(update)
    if not chat_id or not user_id:
        return

    message = update.get("message", {})
    text = message.get("text", "").strip()

    if not text:
        return

    state = _get_user_state(user_id)

    # Handle city search
    if state == "searching_city":
        prefs = get_user_prefs(user_id)
        # Store search query in state for refreshing after toggle
        _set_user_state(user_id, f"search_results:{text}")
        keyboard = _build_search_results_keyboard(text, prefs.get("cities", []))
        send_message_with_keyboard(
            chat_id, f"🔍 תוצאות חיפוש עבור \"{text}\":", keyboard
        )
        return

    # Handle editing blessing/dedication
    if state and state.startswith("editing_"):
        field = state.replace("editing_", "")  # "blessing" or "dedication"

        # Save the text
        prefs = get_user_prefs(user_id)
        prefs[f"{field}_text"] = text
        set_user_prefs(user_id, prefs)

        # Clear state
        _clear_user_state(user_id)

        field_name = "הברכה" if field == "blessing" else "לעילוי נשמת"
        send_message(chat_id, f"✅ {field_name} עודכן!")

        # Show updated settings
        settings_text = format_settings(prefs)
        has_saved_image = bool(prefs.get("last_image_file_id"))
        reminder_enabled = prefs.get("reminder_enabled", False)
        nusach = prefs.get("nusach", "sefard")
        keyboard = _build_settings_keyboard(prefs.get("poster_mode", "shabbat"), has_saved_image, reminder_enabled, nusach)
        send_message_with_keyboard(chat_id, settings_text, keyboard, parse_mode="HTML")
        return

    # No active state - show help menu for unrecognized messages
    help_text = (
        "🤔 לא הבנתי את ההודעה שלך.\n\n"
        "💡 <b>מה אפשר לעשות?</b>\n"
        "• שלח <b>תמונה</b> ואני אצור ממנה פוסטר שבת\n"
        "• לחץ על <b>הגדרות</b> להתאמה אישית\n"
        "• לחץ על <b>צור פוסטר</b> עם תמונת ברירת מחדל\n\n"
        "💻 לתצוגה נגישה ויכולות נוספות, נסו את האתר!"
    )
    keyboard = _build_help_keyboard()
    send_message_with_keyboard(chat_id, help_text, keyboard, parse_mode="HTML")


def process_update(update: Dict[str, Any]) -> None:
    """Process a Telegram update and route to appropriate handler."""
    # Check for callback query first (inline keyboard button press)
    if "callback_query" in update:
        handle_callback_query(update)
        return

    message = update.get("message", {})

    # Check for commands
    text = message.get("text", "")
    if text.startswith("/"):
        command = text.split()[0].lower()
        if command == "/start":
            handle_start(update)
        elif command == "/poster":
            handle_poster(update)
        elif command == "/omer":
            handle_omer(update)
        elif command == "/settings":
            handle_settings(update)
        elif command == "/reset":
            handle_reset(update)
        elif command == "/skip":
            handle_skip(update)
        elif command == "/clear_blessing":
            handle_clear_blessing(update)
        elif command == "/clear_dedication":
            handle_clear_dedication(update)
        elif command == "/clear_memorial":
            handle_clear_dedication(update)  # Alias for /clear_dedication
        elif command == "/clear_image":
            handle_clear_image(update)
        elif command == "/reminder":
            handle_reminder(update)
        elif command == "/help":
            handle_help(update)
        return

    # Check for photo
    if message.get("photo"):
        handle_photo(update)
        return

    # Check for text message (may be part of conversation flow)
    if text:
        handle_text_message(update)
        return


# --- Bot Commands Menu ---


def set_bot_commands() -> Dict[str, Any]:
    """Set the bot's command menu via Telegram API (setMyCommands).

    This registers the command menu that appears when users press / in the chat.
    Call once at setup or via /api/setup_commands endpoint.

    Returns:
        dict: Telegram API response
    """
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setMyCommands"
    commands = [
        {"command": "start", "description": "התחל מחדש"},
        {"command": "poster", "description": "📸 צור פוסטר שבת/עומר"},
        {"command": "omer", "description": "🔢 צור פוסטר ספירת העומר"},
        {"command": "reminder", "description": "🔔 תזכורת יומית לספירה"},
        {"command": "settings", "description": "⚙️ הגדרות"},
        {"command": "help", "description": "📋 עזרה"},
        {"command": "reset", "description": "🔄 איפוס להגדרות ברירת מחדל"},
    ]
    payload = {"commands": commands}
    response = requests.post(url, json=payload, timeout=30)
    return response.json()

