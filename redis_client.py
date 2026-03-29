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
    "last_image_file_id": None,
    "poster_mode": "shabbat"  # "shabbat" or "omer"
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

