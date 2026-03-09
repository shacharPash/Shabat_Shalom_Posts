"""
Telegram bot module for Shabbat poster generation.

Handles all bot commands and photo processing for generating personalized
Shabbat time posters via Telegram.
"""

import base64
import io
import os
from typing import Any, Dict, Optional

import requests

from redis_client import get_user_prefs, set_user_prefs, DEFAULT_PREFERENCES
from api.poster import build_poster_from_payload
from cities import build_city_lookup, get_cities_list

# Load city lookup once at module level
CITY_BY_NAME = build_city_lookup(get_cities_list())

# Bot token from environment
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")


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
        f"🕯 <b>הקדשה:</b> {dedication}\n\n"
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
        "/clear_dedication - נקה טקסט הקדשה\n\n"
        "שלח תמונה כדי להתחיל! 📸"
    )
    send_message(chat_id, welcome_text)


def handle_settings(update: Dict[str, Any]) -> None:
    """Handle /settings command - show current user settings."""
    chat_id = get_chat_id(update)
    user_id = get_user_id(update)
    if not chat_id or not user_id:
        return

    prefs = get_user_prefs(user_id)
    settings_text = format_settings(prefs)
    send_message(chat_id, settings_text)


def handle_reset(update: Dict[str, Any]) -> None:
    """Handle /reset command - reset to default settings."""
    chat_id = get_chat_id(update)
    user_id = get_user_id(update)
    if not chat_id or not user_id:
        return

    set_user_prefs(user_id, DEFAULT_PREFERENCES.copy())
    send_message(chat_id, "✅ ההגדרות אופסו לברירת מחדל.")


def handle_skip(update: Dict[str, Any]) -> None:
    """Handle /skip command - skip text input."""
    chat_id = get_chat_id(update)
    if not chat_id:
        return

    send_message(chat_id, "⏭ דילגת. שלח תמונה ליצירת פוסטר.")


def handle_clear_blessing(update: Dict[str, Any]) -> None:
    """Handle /clear_blessing command - clear blessing text."""
    chat_id = get_chat_id(update)
    user_id = get_user_id(update)
    if not chat_id or not user_id:
        return

    prefs = get_user_prefs(user_id)
    prefs["blessing_text"] = None
    set_user_prefs(user_id, prefs)
    send_message(chat_id, "✅ טקסט הברכה נמחק.")


def handle_clear_dedication(update: Dict[str, Any]) -> None:
    """Handle /clear_dedication command - clear dedication text."""
    chat_id = get_chat_id(update)
    user_id = get_user_id(update)
    if not chat_id or not user_id:
        return

    prefs = get_user_prefs(user_id)
    prefs["dedication_text"] = None
    set_user_prefs(user_id, prefs)
    send_message(chat_id, "✅ טקסט ההקדשה נמחק.")


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


def process_update(update: Dict[str, Any]) -> None:
    """Process a Telegram update and route to appropriate handler."""
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
        return

    # Check for photo
    if message.get("photo"):
        handle_photo(update)
        return

