"""
Redis client module for storing user preferences.

Uses Upstash-compatible Redis (standard redis-py client).
"""

import json
import secrets
import re
from datetime import date
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


def complete_claim(key: str, token: str, ttl: int = DONE_TTL, *, success_key: str | None = None, cleanup_keys=()) -> bool:
    """Record success and release the owned lease in one transaction."""
    return bool(get_redis_client().eval(
        "if redis.call('GET', KEYS[1]) ~= ARGV[1] then return 0 end "
        "redis.call('SET', KEYS[2], '1', 'EX', ARGV[2]); "
        "redis.call('DEL', KEYS[1], KEYS[3]); "
        "for i=4,#KEYS do redis.call('DEL', KEYS[i]) end return 1",
        3 + len(cleanup_keys), key, success_key or key + ':done', key + ':budget',
        *cleanup_keys, token, ttl))


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


REMINDER_PAGE_TTL = 3600
REMINDER_ROOT_TTL = EVENT_TTL
MAX_SCAN_CANDIDATES = 1000
REMINDER_PAGE_PREFIX = 'zmunah:reminder_page:'
SNAPSHOT_LOCK_KEY = 'zmunah:reminder_snapshot_lock'


@contextmanager
def reminder_snapshot_lock():
    """Never acquire/wait for a user lock while holding this snapshot lock."""
    token = acquire_claim(SNAPSHOT_LOCK_KEY)
    if token is None:
        raise RuntimeError('reminder snapshot busy')
    try:
        yield
    finally:
        release_claim(SNAPSHOT_LOCK_KEY, token)


def _read_reminder_page(token, scope=None):
    if not isinstance(token, str) or not re.fullmatch(r'[0-9a-f]{32}', token):
        raise ValueError('invalid reminder cursor')
    raw = get_redis_client().get(REMINDER_PAGE_PREFIX + token)
    if raw is None or len(raw) > 4096:
        raise ValueError('missing or expired reminder cursor')
    page = json.loads(raw)
    if not isinstance(page, dict) or not isinstance(page.get('scope'), str) or len(page['scope']) > 80:
        raise ValueError('invalid reminder page')
    if scope is not None and page['scope'] != scope:
        raise ValueError('mismatched reminder cursor')
    if 'scan' in page:
        if set(page) != {'scope', 'scan'} or not re.fullmatch(r'[0-9]{1,20}', str(page['scan'])):
            raise ValueError('invalid reminder page')
    else:
        if set(page) != {'scope', 'users', 'next'} or not isinstance(page['users'], list) or len(page['users']) > 2:
            raise ValueError('invalid reminder page')
        if any(not isinstance(uid, str) or not re.fullmatch(r'[0-9]{1,20}', uid) for uid in page['users']):
            raise ValueError('invalid reminder page')
        if page['next'] != '0' and not re.fullmatch(r'[0-9a-f]{32}', str(page['next'])):
            raise ValueError('invalid reminder page')
    return page


def _expand_reminder_page(token, page):
    """Consume a SCAN cursor once; atomically save all bounded overflow identities."""
    client = get_redis_client()
    cursor, keys = client.scan(int(page['scan']), match=USER_PREFS_KEY_PREFIX + '*', count=20)
    if len(keys) > MAX_SCAN_CANDIDATES:
        raise ValueError('reminder scan page exceeds limit')
    users = sorted({key[len(USER_PREFS_KEY_PREFIX):] for key in keys
                    if re.fullmatch(r'zmunah:user:[0-9]{1,20}', key)})
    groups = [users[i:i + 2] for i in range(0, len(users), 2)] or [[]]
    tokens = [token] + [secrets.token_hex(16) for _ in groups[1:]]
    continuation = secrets.token_hex(16) if cursor else '0'
    records = []
    for index, group in enumerate(groups):
        next_token = tokens[index + 1] if index + 1 < len(tokens) else continuation
        records.append((tokens[index], {'scope': page['scope'], 'users': group, 'next': next_token}))
    if cursor:
        records.append((continuation, {'scope': page['scope'], 'scan': str(cursor)}))
    with client.pipeline(transaction=True) as pipe:
        for page_token, record in records:
            pipe.set(REMINDER_PAGE_PREFIX + page_token, json.dumps(record), ex=REMINDER_PAGE_TTL)
        pipe.execute()
    return records[0][1]


def _remove_user_from_reminder_pages(user_id):
    """Called only with the snapshot lock, including throughout owned deletion."""
    client = get_redis_client()
    for key in client.scan_iter(match=REMINDER_PAGE_PREFIX + '*', count=100):
        raw = client.get(key)
        if raw is None:
            continue
        page = _read_reminder_page(key[len(REMINDER_PAGE_PREFIX):])
        if user_id in page.get('users', []):
            page['users'] = [uid for uid in page['users'] if uid != user_id]
            # Preserve its original expiry and linked position; no positional offset.
            client.set(key, json.dumps(page), xx=True, keepttl=True)


def delete_user_data(user_id: str, preserve_keys=()) -> None:
    """Remove owned records and saved recipient membership under the snapshot lock."""
    client = get_redis_client()
    with reminder_snapshot_lock():
        keys = [key for key in user_data_keys(user_id) if key not in preserve_keys]
        for start in range(0, len(keys), 100):
            client.delete(*keys[start:start + 100])
        _remove_user_from_reminder_pages(str(user_id))


def reminder_user_batch(field: str, cursor: str = '0', limit: int = 2, *, scope: str | None = None) -> tuple[list[str], str]:
    """Read a stable two-candidate page; retries preserve exact recipient identity.

    Zero selects the existing event root or initializes it. Other cursors are
    opaque saved-page tokens. Expired/missing saved pages fail closed.
    """
    if field not in ('reminder_enabled', 'shabbat_reminder_enabled') or limit != 2:
        raise ValueError('invalid reminder batch configuration')
    scope = scope or field + ':' + date.today().isoformat()
    if not re.fullmatch(r'[a-z_]+:[0-9-]{10}', scope):
        raise ValueError('invalid reminder scope')
    client = get_redis_client()
    with reminder_snapshot_lock():
        if cursor == '0' or (isinstance(cursor, str) and re.fullmatch(r'r\.[0-9a-f]{32}', cursor)):
            root_key = 'zmunah:reminder_root:' + scope
            if cursor != '0':
                root_key += ':restart:' + cursor[2:]
            token = client.get(root_key)
            if token is None:
                token = secrets.token_hex(16)
                with client.pipeline(transaction=True) as pipe:
                    pipe.set(REMINDER_PAGE_PREFIX + token,
                             json.dumps({'scope': scope, 'scan': '0'}), ex=REMINDER_PAGE_TTL)
                    pipe.set(root_key, token, ex=REMINDER_ROOT_TTL)
                    pipe.execute()
        else:
            token = cursor
        page = _read_reminder_page(token, scope)
        if 'scan' in page:
            page = _expand_reminder_page(token, page)
        if page['next'] != '0':
            _read_reminder_page(page['next'], scope)
        candidates = page['users']
        continuation = page['next']
    # The global page lock has been released before any user lock can be taken.
    users = [uid for uid in candidates if get_user_prefs(uid).get(field) is True]
    return users, continuation


def get_pending_deletion(user_id):
    raw = get_redis_client().get(f'zmunah:privacy:{user_id}:delete_pending')
    if raw is None:
        return None
    pending = json.loads(raw)
    if not isinstance(pending, dict) or not re.fullmatch(r'[0-9a-f]{24}', str(pending.get('nonce', ''))) or type(pending.get('update_id')) is not int:
        raise ValueError('invalid pending deletion')
    return pending


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
