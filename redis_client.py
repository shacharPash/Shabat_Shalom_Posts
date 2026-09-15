"""
Redis client module for storing user preferences.

Uses Upstash-compatible Redis (standard redis-py client).
"""

import json
import secrets
from copy import deepcopy
from contextvars import ContextVar
from contextlib import contextmanager
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

    _redis_client = redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=3, socket_timeout=5, retry_on_timeout=False)
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
        return deepcopy(DEFAULT_PREFERENCES)
    
    try:
        prefs = json.loads(data)
        # Merge with defaults to ensure all keys exist
        result = deepcopy(DEFAULT_PREFERENCES)
        result.update(prefs if isinstance(prefs, dict) else {})
        return result
    except json.JSONDecodeError:
        return deepcopy(DEFAULT_PREFERENCES)


def set_user_prefs(user_id: str, prefs: Dict[str, Any]) -> None:
    """
    Save user preferences to Redis.

    Args:
        user_id: The Telegram user ID
        prefs: Dictionary of user preferences
    """
    def reset(current):
        current.clear()
        current.update(deepcopy(prefs))
    mutate_user_prefs(user_id, reset)


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


# Key pattern for Omer counted tracking
OMER_COUNTED_KEY_PREFIX = "zmunah:omer_counted:"


def mark_omer_counted(user_id: str, omer_day: int | str) -> None:
    """
    Mark that a user has counted the Omer for a specific day.

    Args:
        user_id: The Telegram user ID
        omer_day: The event date (YYYY-MM-DD), or a legacy day number (1-49)
    """
    client = get_redis_client()
    key = f"{OMER_COUNTED_KEY_PREFIX}{user_id}:{omer_day}"
    # Set with 48-hour expiration to auto-cleanup old keys
    client.setex(key, 48 * 60 * 60, "1")


def was_omer_counted(user_id: str, omer_day: int | str) -> bool:
    """
    Check if a user has already marked the Omer as counted for a specific day.

    Args:
        user_id: The Telegram user ID
        omer_day: The event date (YYYY-MM-DD), or a legacy day number (1-49)

    Returns:
        bool: True if already marked as counted, False otherwise
    """
    client = get_redis_client()
    key = f"{OMER_COUNTED_KEY_PREFIX}{user_id}:{omer_day}"
    return client.exists(key) == 1


# Processing leases outlive the deployment's 300 second request limit.
CLAIM_TTL = 600
DONE_TTL = 7 * 24 * 60 * 60
EVENT_TTL = 72 * 60 * 60


_preference_operation = ContextVar('preference_operation', default=None)


@contextmanager
def preference_operation(user_id, update_id):
    """Stable per-update mutation receipts prevent retrying a toggle twice."""
    token = _preference_operation.set([str(user_id), str(update_id), 0])
    try:
        yield
    finally:
        _preference_operation.reset(token)


def mutate_user_prefs(user_id: str, mutation, retries: int = 64) -> Dict[str, Any]:
    """Apply a pure in-place mutation under WATCH/MULTI. May call it again on conflict."""
    client = get_redis_client()
    key = f"{USER_PREFS_KEY_PREFIX}{user_id}"
    operation = _preference_operation.get()
    receipt = None
    if operation is not None and operation[0] == str(user_id):
        operation[2] += 1
        receipt = f"zmunah:delivery:{user_id}:update:{operation[1]}:mutation:{operation[2]}"
    for _ in range(retries):
        with client.pipeline() as pipe:
            try:
                pipe.watch(key, *([receipt] if receipt else []))
                if receipt and pipe.exists(receipt):
                    return get_user_prefs(user_id)
                raw = pipe.get(key)
                prefs = deepcopy(DEFAULT_PREFERENCES)
                if raw:
                    saved = json.loads(raw)
                    if isinstance(saved, dict):
                        prefs.update(saved)
                mutation(prefs)
                pipe.multi()
                pipe.set(key, json.dumps(prefs, ensure_ascii=False))
                if receipt:
                    pipe.set(receipt, "1", ex=DONE_TTL)
                pipe.execute()
                return prefs
            except redis.WatchError:
                continue
    raise redis.WatchError("preference update contention")


def update_user_prefs(user_id: str, changes: Dict[str, Any]) -> Dict[str, Any]:
    """Atomically merge independent fields, preserving legacy JSON and unknown fields."""
    return mutate_user_prefs(user_id, lambda prefs: prefs.update(deepcopy(changes)))


def acquire_claim(key: str, ttl: int = CLAIM_TTL, *, success_key: str | None = None) -> Optional[str]:
    """Claim unfinished work atomically. Storage errors propagate without doing work."""
    token = secrets.token_hex(16)
    acquired = get_redis_client().eval(
        "if redis.call('EXISTS', KEYS[2]) == 1 then return 0 end "
        "return redis.call('SET', KEYS[1], ARGV[1], 'NX', 'EX', ARGV[2])",
        2, key, success_key or key + ':done', token, ttl)
    return token if acquired else None


def release_claim(key: str, token: str) -> bool:
    """Release only this worker's lease, including after another lease replaced it."""
    return bool(get_redis_client().eval(
        "if redis.call('GET', KEYS[1]) == ARGV[1] then "
        "return redis.call('DEL', KEYS[1]) end return 0", 1, key, token))


def complete_claim(key: str, token: str, ttl: int = DONE_TTL, *, success_key: str | None = None) -> bool:
    """Record success and release the owned lease in one transaction."""
    return bool(get_redis_client().eval(
        "if redis.call('GET', KEYS[1]) ~= ARGV[1] then return 0 end "
        "redis.call('SET', KEYS[2], '1', 'EX', ARGV[2]); "
        "redis.call('DEL', KEYS[1], KEYS[3]); return 1",
        3, key, success_key or key + ':done', key + ':budget', token, ttl))


def claim_completed(key: str, *, success_key: str | None = None) -> bool:
    return bool(get_redis_client().exists(success_key or key + ':done'))


def user_data_keys(user_id: str) -> list[str]:
    """Exact user ownership, including legacy sent/count keys. Never substring matching."""
    if not str(user_id).isdigit():
        raise ValueError("invalid user")
    client = get_redis_client()
    keys = {f"zmunah:user:{user_id}", f"zmunah:state:{user_id}"}
    for pattern in (f"zmunah:delivery:{user_id}:*", f"zmunah:omer_sent:*:{user_id}",
                    f"zmunah:omer_counted:{user_id}:*", f"zmunah:privacy:{user_id}:*"):
        keys.update(client.scan_iter(match=pattern, count=100))
    return sorted(keys)


def export_user_data(user_id: str) -> dict:
    """Return only stored values owned by this user, excluding privacy flow metadata."""
    client = get_redis_client()
    result = {}
    for key in user_data_keys(user_id):
        if ':privacy:' in key or ':update:' in key or key.endswith((':processing', ':rate')):
            continue
        value = client.get(key)
        if value is not None:
            try:
                value = json.loads(value)
            except (ValueError, TypeError):
                pass
            result[key] = value
    return result


def delete_user_data(user_id: str, preserve_keys=()) -> None:
    """Remove owned data. A missing preference record has reminders disabled by default."""
    client = get_redis_client()
    keys = [key for key in user_data_keys(user_id) if key not in preserve_keys]
    for start in range(0, len(keys), 100):
        client.delete(*keys[start:start + 100])


def reminder_user_batch(field: str, cursor: str = '0', limit: int = 2) -> tuple[list[str], str]:
    """Bound sends even when Redis SCAN returns more than its COUNT hint.

    Cursor stores the SCAN position and offset within that returned page. Page
    contents can change during scanning; completed event claims make repeats safe.
    """
    if field not in ('reminder_enabled', 'shabbat_reminder_enabled'):
        raise ValueError('invalid reminder field')
    parts = cursor.split(':')
    scan_cursor = int(parts[0])
    offset = int(parts[1]) if len(parts) == 2 else 0
    if scan_cursor < 0 or offset < 0 or len(parts) > 2:
        raise ValueError('invalid cursor')
    client = get_redis_client()
    next_cursor, keys = client.scan(scan_cursor, match=USER_PREFS_KEY_PREFIX + '*', count=20)
    keys = sorted(keys)
    users = []
    stop = min(offset + 20, len(keys))
    for position in range(offset, stop):
        user_id = keys[position][len(USER_PREFS_KEY_PREFIX):]
        if user_id.isdigit() and get_user_prefs(user_id).get(field) is True:
            users.append(user_id)
        if len(users) == limit:
            next_position = position + 1
            resume = f'{scan_cursor}:{next_position}' if next_position < len(keys) else str(next_cursor)
            return users, resume
    return users, (f"{scan_cursor}:{stop}" if stop < len(keys) else str(next_cursor))


def consume_update_budget(user_id: str, receipt_key: str, limit: int = 30, window: int = 60) -> bool:
    """Count each authenticated update once against its actor's fixed window."""
    key = f'zmunah:delivery:{user_id}:rate'
    return bool(get_redis_client().eval(
        "if redis.call('EXISTS', KEYS[2]) == 1 then return 1 end "
        "local current = tonumber(redis.call('GET', KEYS[1]) or '0'); "
        "if current >= tonumber(ARGV[1]) then return 0 end "
        "local count = redis.call('INCR', KEYS[1]); "
        "if count == 1 then redis.call('EXPIRE', KEYS[1], ARGV[2]) end "
        "redis.call('SET', KEYS[2], '1', 'EX', ARGV[3]); return 1",
        2, key, receipt_key, limit, window, DONE_TTL))
