"""
Telegram bot module for Shabbat poster generation.

Handles all bot commands and photo processing for generating personalized
Shabbat time posters via Telegram.
"""

import base64
import io
import os
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


def _build_settings_keyboard() -> List[List[Dict[str, str]]]:
    """Build the main settings inline keyboard."""
    return [
        [{"text": "🏙️ ערוך ערים", "callback_data": "edit:cities"}],
        [{"text": "📅 פורמט תאריך", "callback_data": "edit:date"}],
        [
            {"text": "💬 ערוך ברכה", "callback_data": "edit:blessing"},
            {"text": "🕯️ לעילוי נשמת", "callback_data": "edit:dedication"},
        ],
    ]


CITIES_PER_PAGE = 12


def _build_cities_keyboard(
    selected_cities: List[Dict[str, Any]], page: int = 0
) -> List[List[Dict[str, str]]]:
    """Build city selection grid with toggles and pagination."""
    selected_names = {
        c.get("name", c) if isinstance(c, dict) else c for c in selected_cities
    }

    total_cities = len(AVAILABLE_CITIES)
    total_pages = (total_cities + CITIES_PER_PAGE - 1) // CITIES_PER_PAGE
    page = max(0, min(page, total_pages - 1))  # Clamp to valid range

    start = page * CITIES_PER_PAGE
    end = min(start + CITIES_PER_PAGE, total_cities)

    buttons = []
    row = []
    for city in AVAILABLE_CITIES[start:end]:
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
    buttons.append([{"text": "🔍 חפש עיר", "callback_data": "cities:search"}])
    buttons.append([{"text": "✅ סיום", "callback_data": "cities:done"}])
    return buttons


def _build_search_results_keyboard(
    query: str, selected_cities: List[Dict[str, Any]]
) -> List[List[Dict[str, str]]]:
    """Build keyboard with search results."""
    selected_names = {
        c.get("name", c) if isinstance(c, dict) else c for c in selected_cities
    }

    # Search for matching cities
    query_lower = query.lower()
    matches = [c for c in AVAILABLE_CITIES if query_lower in c["name"].lower()]

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
    
    return (
        "⚙️ <b>ההגדרות שלך:</b>\n\n"
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
        "🕯️ <b>שבת שלום!</b>\n\n"
        "אני בוט שיעזור לך ליצור פוסטרים יפים עם זמני השבת.\n\n"
        "<b>איך להשתמש:</b>\n"
        "1️⃣ שלח לי תמונה\n"
        "2️⃣ אני אוסיף את זמני השבת והפרשה\n"
        "3️⃣ תקבל פוסטר מוכן לשיתוף!\n\n"
        "<b>פקודות:</b>\n"
        "/settings - צפה בהגדרות שלך\n"
        "/reset - אפס להגדרות ברירת מחדל\n"
        "/clear_blessing - נקה טקסט ברכה\n"
        "/clear_memorial - נקה לעילוי נשמת\n\n"
        "שלח תמונה כדי להתחיל! 📸"
    )
    keyboard = [
        [
            {"text": "⚙️ הגדרות", "callback_data": "start:settings"},
            {"text": "🔄 איפוס", "callback_data": "start:reset"},
        ]
    ]
    send_message_with_keyboard(chat_id, welcome_text, keyboard, parse_mode="HTML")


def handle_settings(update: Dict[str, Any]) -> None:
    """Handle /settings command - show preview poster then settings with inline keyboard."""
    chat_id = get_chat_id(update)
    user_id = get_user_id(update)
    if not chat_id or not user_id:
        return

    prefs = get_user_prefs(user_id)

    # Generate preview poster with current settings (uses default image)
    try:
        preview_payload = {
            "dateFormat": prefs.get("date_format", "both"),
        }

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
        send_photo(chat_id, poster_bytes, "👆 כך ייראה הפוסטר שלך עם ההגדרות הנוכחיות")
    except Exception:
        # If preview fails, continue to show settings menu
        pass

    # Show settings menu
    settings_text = format_settings(prefs)
    keyboard = _build_settings_keyboard()
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
        keyboard = _build_settings_keyboard()
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

        # Build payload for poster generation
        payload = {
            "imageBase64": base64.b64encode(photo_bytes).decode("utf-8"),
            "dateFormat": prefs.get("date_format", "both"),
        }

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

        # Send poster back to user
        send_photo(chat_id, poster_bytes, "🕯️ הפוסטר שלך מוכן! שבת שלום!")

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
        "🔍 הקלד שם עיר לחיפוש:\n(או /skip לביטול)",
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


def handle_settings_back(chat_id: int, message_id: int, user_id: str) -> None:
    """Return to main settings view."""
    prefs = get_user_prefs(user_id)
    settings_text = format_settings(prefs)
    keyboard = _build_settings_keyboard()
    edit_message_with_keyboard(chat_id, message_id, settings_text, keyboard, parse_mode="HTML")


def handle_start_settings(chat_id: int, user_id: str) -> None:
    """Handle start:settings callback - send settings as new message."""
    prefs = get_user_prefs(user_id)
    settings_text = format_settings(prefs)
    keyboard = _build_settings_keyboard()
    send_message_with_keyboard(chat_id, settings_text, keyboard, parse_mode="HTML")


def handle_start_reset(chat_id: int, user_id: str) -> None:
    """Handle start:reset callback - reset to default settings."""
    set_user_prefs(user_id, DEFAULT_PREFERENCES.copy())
    send_message(chat_id, "✅ ההגדרות אופסו לברירת מחדל.")


def handle_text_message(update: Dict[str, Any]) -> None:
    """Handle text messages - check if user is in editing or searching state."""
    chat_id = get_chat_id(update)
    user_id = get_user_id(update)
    if not chat_id or not user_id:
        return

    state = _get_user_state(user_id)
    if not state:
        return  # No active state, ignore

    message = update.get("message", {})
    text = message.get("text", "").strip()

    if not text:
        return

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
    if state.startswith("editing_"):
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
        keyboard = _build_settings_keyboard()
        send_message_with_keyboard(chat_id, settings_text, keyboard, parse_mode="HTML")


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
        {"command": "settings", "description": "⚙️ הגדרות"},
        {"command": "help", "description": "📋 עזרה"},
        {"command": "reset", "description": "🔄 איפוס להגדרות ברירת מחדל"},
    ]
    payload = {"commands": commands}
    response = requests.post(url, json=payload, timeout=30)
    return response.json()

