"""
Telegram bot settings module - Inline keyboard UI and conversation flow.

Provides settings display, city selection, date format selection,
and text editing (blessing/dedication) via conversation flow.
"""

from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    CallbackQueryHandler,
    MessageHandler,
    CommandHandler,
    filters,
)

from redis_client import get_redis_client, get_user_prefs, set_user_prefs
from cities import get_cities_list

# State key pattern for conversation flow
USER_STATE_KEY = "zmunah:state:{user_id}"

# Date format display names
DATE_FORMAT_LABELS = {
    "hebrew": "עברי",
    "gregorian": "לועזי", 
    "both": "שניהם",
}


def _get_user_state(user_id: int) -> Optional[str]:
    """Get user's current conversation state from Redis."""
    client = get_redis_client()
    key = USER_STATE_KEY.format(user_id=user_id)
    return client.get(key)


def _set_user_state(user_id: int, state: Optional[str]) -> None:
    """Set user's conversation state in Redis. None clears the state."""
    client = get_redis_client()
    key = USER_STATE_KEY.format(user_id=user_id)
    if state is None:
        client.delete(key)
    else:
        client.set(key, state, ex=3600)  # Expire after 1 hour


def _build_settings_message(prefs: dict) -> str:
    """Build the settings display message."""
    # Format cities
    cities_list = prefs.get("cities", [])
    if cities_list:
        city_names = [c.get("name", c) if isinstance(c, dict) else c for c in cities_list]
        cities_str = ", ".join(city_names)
    else:
        cities_str = "(לא נבחרו)"
    
    # Format date
    date_format = prefs.get("date_format", "both")
    date_str = DATE_FORMAT_LABELS.get(date_format, date_format)
    
    # Format blessing/dedication
    blessing = prefs.get("blessing_text") or "(ללא)"
    dedication = prefs.get("dedication_text") or "(ללא)"
    
    return (
        f"⚙️ ההגדרות שלך:\n\n"
        f"🏙️ ערים: {cities_str}\n"
        f"📅 פורמט: {date_str}\n"
        f"💬 ברכה: {blessing}\n"
        f"🕯️ הקדשה: {dedication}"
    )


def _build_settings_keyboard() -> InlineKeyboardMarkup:
    """Build the main settings inline keyboard."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏙️ ערוך ערים", callback_data="settings:cities")],
        [InlineKeyboardButton("📅 פורמט תאריך", callback_data="settings:date")],
        [
            InlineKeyboardButton("💬 ערוך ברכה", callback_data="edit:blessing"),
            InlineKeyboardButton("🕯️ ערוך הקדשה", callback_data="edit:dedication"),
        ],
    ])


def _build_cities_keyboard(selected_cities: list) -> InlineKeyboardMarkup:
    """Build city selection grid with toggles."""
    cities = get_cities_list()
    selected_names = {c.get("name", c) if isinstance(c, dict) else c for c in selected_cities}
    
    buttons = []
    row = []
    # Show top 15 cities for reasonable grid size
    for city in cities[:15]:
        name = city["name"]
        prefix = "✓ " if name in selected_names else ""
        row.append(InlineKeyboardButton(f"{prefix}{name}", callback_data=f"city:{name}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    
    buttons.append([InlineKeyboardButton("✅ סיום", callback_data="settings:done")])
    return InlineKeyboardMarkup(buttons)


def _build_date_format_keyboard(current: str) -> InlineKeyboardMarkup:
    """Build date format selection keyboard."""
    buttons = []
    for fmt, label in DATE_FORMAT_LABELS.items():
        prefix = "✓ " if fmt == current else ""
        buttons.append(InlineKeyboardButton(f"{prefix}{label}", callback_data=f"date:{fmt}"))
    return InlineKeyboardMarkup([buttons, [InlineKeyboardButton("⬅️ חזרה", callback_data="settings:back")]])


async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /settings command - show current settings with edit buttons."""
    user_id = str(update.effective_user.id)
    prefs = get_user_prefs(user_id)
    message = _build_settings_message(prefs)
    keyboard = _build_settings_keyboard()
    await update.message.reply_text(message, reply_markup=keyboard)


async def settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline keyboard callbacks for settings."""
    query = update.callback_query
    await query.answer()
    
    user_id = str(update.effective_user.id)
    prefs = get_user_prefs(user_id)
    data = query.data
    
    if data == "settings:cities":
        keyboard = _build_cities_keyboard(prefs.get("cities", []))
        await query.edit_message_text("🏙️ בחר ערים (לחץ להוספה/הסרה):", reply_markup=keyboard)
    
    elif data == "settings:date":
        keyboard = _build_date_format_keyboard(prefs.get("date_format", "both"))
        await query.edit_message_text("📅 בחר פורמט תאריך:", reply_markup=keyboard)
    
    elif data in ("settings:done", "settings:back"):
        message = _build_settings_message(prefs)
        keyboard = _build_settings_keyboard()
        await query.edit_message_text(message, reply_markup=keyboard)


async def city_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle city toggle callbacks."""
    query = update.callback_query
    await query.answer()

    user_id = str(update.effective_user.id)
    prefs = get_user_prefs(user_id)
    city_name = query.data.split(":", 1)[1]

    # Get current cities as list of names
    current_cities = prefs.get("cities", [])
    current_names = [c.get("name", c) if isinstance(c, dict) else c for c in current_cities]

    # Toggle city
    if city_name in current_names:
        # Remove city
        prefs["cities"] = [c for c in current_cities
                          if (c.get("name", c) if isinstance(c, dict) else c) != city_name]
    else:
        # Add city with default offset
        from cities import SPECIAL_OFFSET_CITIES, DEFAULT_CANDLE_OFFSET
        offset = SPECIAL_OFFSET_CITIES.get(city_name, DEFAULT_CANDLE_OFFSET)
        prefs["cities"].append({"name": city_name, "candle_offset": offset})

    set_user_prefs(user_id, prefs)

    # Refresh keyboard
    keyboard = _build_cities_keyboard(prefs.get("cities", []))
    await query.edit_message_reply_markup(reply_markup=keyboard)


async def date_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle date format selection callbacks."""
    query = update.callback_query
    await query.answer()

    user_id = str(update.effective_user.id)
    prefs = get_user_prefs(user_id)
    date_format = query.data.split(":", 1)[1]

    prefs["date_format"] = date_format
    set_user_prefs(user_id, prefs)

    # Show updated keyboard
    keyboard = _build_date_format_keyboard(date_format)
    await query.edit_message_reply_markup(reply_markup=keyboard)


async def edit_text_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle edit blessing/dedication callbacks - start conversation flow."""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    field = query.data.split(":", 1)[1]  # "blessing" or "dedication"

    # Set state in Redis
    _set_user_state(user_id, f"editing_{field}")

    field_name = "ברכה" if field == "blessing" else "הקדשה"
    clear_cmd = f"/clear_{field}"
    await query.edit_message_text(
        f"📝 שלח את טקסט ה{field_name} הרצוי\n"
        f"(או /skip לדלג, {clear_cmd} למחיקה)"
    )


async def text_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text messages - check if user is in editing state."""
    user_id = update.effective_user.id
    state = _get_user_state(user_id)

    if not state or not state.startswith("editing_"):
        return  # Not in editing mode

    field = state.replace("editing_", "")  # "blessing" or "dedication"
    text = update.message.text.strip()

    # Save the text
    prefs = get_user_prefs(str(user_id))
    prefs[f"{field}_text"] = text
    set_user_prefs(str(user_id), prefs)

    # Clear state
    _set_user_state(user_id, None)

    field_name = "הברכה" if field == "blessing" else "ההקדשה"
    await update.message.reply_text(f"✅ {field_name} עודכנה!")

    # Show updated settings
    message = _build_settings_message(prefs)
    keyboard = _build_settings_keyboard()
    await update.message.reply_text(message, reply_markup=keyboard)


async def skip_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /skip command - cancel text editing."""
    user_id = update.effective_user.id
    state = _get_user_state(user_id)

    if state and state.startswith("editing_"):
        _set_user_state(user_id, None)
        await update.message.reply_text("⏭️ דילגת על העריכה")

        # Show settings
        prefs = get_user_prefs(str(user_id))
        message = _build_settings_message(prefs)
        keyboard = _build_settings_keyboard()
        await update.message.reply_text(message, reply_markup=keyboard)
    else:
        await update.message.reply_text("אין מה לדלג - אתה לא במצב עריכה")


async def clear_blessing_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /clear_blessing command."""
    user_id = str(update.effective_user.id)
    prefs = get_user_prefs(user_id)
    prefs["blessing_text"] = None
    set_user_prefs(user_id, prefs)

    # Clear any editing state
    _set_user_state(update.effective_user.id, None)

    await update.message.reply_text("✅ הברכה נמחקה")


async def clear_dedication_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /clear_dedication command."""
    user_id = str(update.effective_user.id)
    prefs = get_user_prefs(user_id)
    prefs["dedication_text"] = None
    set_user_prefs(user_id, prefs)

    # Clear any editing state
    _set_user_state(update.effective_user.id, None)

    await update.message.reply_text("✅ ההקדשה נמחקה")


def get_settings_handlers():
    """Return list of handlers to register with the bot application."""
    return [
        CommandHandler("settings", settings_command),
        CommandHandler("skip", skip_command),
        CommandHandler("clear_blessing", clear_blessing_command),
        CommandHandler("clear_dedication", clear_dedication_command),
        CallbackQueryHandler(settings_callback, pattern=r"^settings:"),
        CallbackQueryHandler(city_callback, pattern=r"^city:"),
        CallbackQueryHandler(date_callback, pattern=r"^date:"),
        CallbackQueryHandler(edit_text_callback, pattern=r"^edit:"),
        # Text handler for conversation flow - use low group to allow other handlers first
        MessageHandler(filters.TEXT & ~filters.COMMAND, text_message_handler),
    ]

