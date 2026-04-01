"""
Redis client module for storing user preferences.

Uses Upstash-compatible Redis (standard redis-py client).
"""

import json
import os
from typing import Any, Dict, Optional

import redis

# Key pattern for user preferences
USER_PREFS_KEY_PREFIX = "zmunah:user:"

# Default preferences structure
DEFAULT_PREFERENCES: Dict[str, Any] = {
    "cities": [
        {"name": "ירושלים", "candle_offset": 40},
        {"name": "תל אביב -יפו", "candle_offset": 20},
        {"name": "חיפה", "candle_offset": 20}
    ],
    "date_format": "both",
    "blessing_text": None,
    "dedication_text": None,
    "last_image_file_id": None,  # Backward compatibility
    "shabbat_image_file_id": None,  # Separate image for Shabbat posters
    "omer_image_file_id": None,  # Separate image for Omer posters
    "poster_mode": "shabbat",  # "shabbat" or "omer"
    "reminder_enabled": False,  # Daily Omer reminder
    "reminder_type": "image",  # Omer reminder type: "text" or "image"
    "nusach": "sefard",  # Omer nusach: "sefard", "ashkenaz", or "edot_hamizrach"
    "shabbat_reminder_enabled": False  # Shabbat/Holiday Eve reminder
}

# Cached Redis client
_redis_client: Optional[redis.Redis] = None


def get_redis_client() -> redis.Redis:
    """
    Get Redis connection using REDIS_URL or KV_URL environment variable.

    Supports both standard Redis URL (REDIS_URL) and Vercel KV integration (KV_URL).

    Returns:
        redis.Redis: Redis client instance

    Raises:
        ValueError: If neither REDIS_URL nor KV_URL environment variable is set
    """
    global _redis_client

    if _redis_client is not None:
        return _redis_client

    redis_url = os.getenv("REDIS_URL") or os.getenv("KV_URL")
    if not redis_url:
        raise ValueError("REDIS_URL or KV_URL environment variable is not set")

    _redis_client = redis.from_url(redis_url, decode_responses=True)
    return _redis_client


def get_user_prefs(user_id: str) -> Dict[str, Any]:
    """
    Get user preferences from Redis.
    
    Args:
        user_id: The Telegram user ID
        
    Returns:
        dict: User preferences, or default preferences if not found
    """
    client = get_redis_client()
    key = f"{USER_PREFS_KEY_PREFIX}{user_id}"
    
    data = client.get(key)
    if data is None:
        return DEFAULT_PREFERENCES.copy()
    
    try:
        prefs = json.loads(data)
        # Merge with defaults to ensure all keys exist
        result = DEFAULT_PREFERENCES.copy()
        result.update(prefs)
        return result
    except json.JSONDecodeError:
        return DEFAULT_PREFERENCES.copy()


def set_user_prefs(user_id: str, prefs: Dict[str, Any]) -> None:
    """
    Save user preferences to Redis.

    Args:
        user_id: The Telegram user ID
        prefs: Dictionary of user preferences
    """
    client = get_redis_client()
    key = f"{USER_PREFS_KEY_PREFIX}{user_id}"

    client.set(key, json.dumps(prefs, ensure_ascii=False))


def get_users_with_reminders_enabled() -> list:
    """
    Get all user IDs that have reminder_enabled=True.

    Uses Redis SCAN to iterate over all user keys efficiently.

    Returns:
        list: List of user IDs (as strings) with reminders enabled
    """
    client = get_redis_client()
    pattern = f"{USER_PREFS_KEY_PREFIX}*"
    users_with_reminders = []

    # Use SCAN for efficient iteration
    cursor = 0
    while True:
        cursor, keys = client.scan(cursor, match=pattern, count=100)
        for key in keys:
            data = client.get(key)
            if data:
                try:
                    prefs = json.loads(data)
                    if prefs.get("reminder_enabled", False):
                        # Extract user_id from key
                        if isinstance(key, bytes):
                            key = key.decode('utf-8')
                        user_id = key.replace(USER_PREFS_KEY_PREFIX, "")
                        users_with_reminders.append(user_id)
                except json.JSONDecodeError:
                    continue
        if cursor == 0:
            break

    return users_with_reminders


def get_users_with_shabbat_reminders_enabled() -> list:
    """
    Get all user IDs that have shabbat_reminder_enabled=True.

    Uses Redis SCAN to iterate over all user keys efficiently.

    Returns:
        list: List of user IDs (as strings) with Shabbat/Holiday reminders enabled
    """
    client = get_redis_client()
    pattern = f"{USER_PREFS_KEY_PREFIX}*"
    users_with_reminders = []

    # Use SCAN for efficient iteration
    cursor = 0
    while True:
        cursor, keys = client.scan(cursor, match=pattern, count=100)
        for key in keys:
            data = client.get(key)
            if data:
                try:
                    prefs = json.loads(data)
                    if prefs.get("shabbat_reminder_enabled", False):
                        # Extract user_id from key
                        if isinstance(key, bytes):
                            key = key.decode('utf-8')
                        user_id = key.replace(USER_PREFS_KEY_PREFIX, "")
                        users_with_reminders.append(user_id)
                except json.JSONDecodeError:
                    continue
        if cursor == 0:
            break

    return users_with_reminders


# Key pattern for Omer sent tracking (prevents duplicate reminders per day)
OMER_SENT_KEY_PREFIX = "zmunah:omer_sent:"


def mark_omer_sent_today(user_id: str, date_str: str) -> None:
    """
    Mark that Omer reminder was sent to a user for a specific date.

    Args:
        user_id: The Telegram user ID
        date_str: The date string in YYYY-MM-DD format
    """
    client = get_redis_client()
    key = f"{OMER_SENT_KEY_PREFIX}{date_str}:{user_id}"
    # Set with 48-hour expiration to auto-cleanup old keys
    client.setex(key, 48 * 60 * 60, "1")


def was_omer_sent_today(user_id: str, date_str: str) -> bool:
    """
    Check if Omer reminder was already sent to a user for a specific date.

    Args:
        user_id: The Telegram user ID
        date_str: The date string in YYYY-MM-DD format

    Returns:
        bool: True if reminder was already sent, False otherwise
    """
    client = get_redis_client()
    key = f"{OMER_SENT_KEY_PREFIX}{date_str}:{user_id}"
    return client.exists(key) == 1

