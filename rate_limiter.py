"""
Redis fixed-window quota with a bounded local sliding-window fallback.

Missing configuration permits secret-free local use. Configured Redis failures
raise RateLimitUnavailable so the public adapter can decline rendering.
"""

import os
import time
from threading import Lock
from typing import Tuple

# Store at most this many active identifier/window pairs per process. Never evict
# an active quota to admit a new identifier, which would let churn reset limits.
MAX_MEMORY_IDENTIFIERS = 4096
_memory_store: dict[tuple[str, int], list[float]] = {}
_memory_lock = Lock()


class RateLimitUnavailable(RuntimeError):
    """The quota cannot be enforced; public rendering must be declined."""


def _get_redis_client():
    """Only absent configuration selects local mode, never a storage error."""
    if not (os.getenv("REDIS_URL") or os.getenv("KV_URL")):
        return None
    try:
        from redis_client import get_redis_client
        return get_redis_client()
    except Exception:
        raise RateLimitUnavailable("Rate limit unavailable") from None


def _cleanup_memory_store(current_time: float) -> None:
    """On each local request, remove expired timestamps and identifiers."""
    for key, timestamps in list(_memory_store.items()):
        active = [ts for ts in timestamps if ts > current_time - key[1]]
        if active:
            _memory_store[key] = active
        else:
            del _memory_store[key]


def _check_rate_limit_redis(
    redis_client,
    key: str,
    max_requests: int,
    window_seconds: int
) -> Tuple[bool, int]:
    """
    Check rate limit using Redis.
    
    Returns:
        Tuple[bool, int]: (is_allowed, remaining_requests)
    """
    current_time = int(time.time())
    window_key = f"ratelimit:{key}:{current_time // window_seconds}"
    
    try:
        pipe = redis_client.pipeline()
        pipe.incr(window_key)
        pipe.expire(window_key, window_seconds)
        results = pipe.execute()
        
        current_count = results[0]
        remaining = max(0, max_requests - current_count)
        is_allowed = current_count <= max_requests
        
        return is_allowed, remaining
    except Exception:
        raise RateLimitUnavailable("Rate limit unavailable") from None


def _check_rate_limit_memory(
    key: str,
    max_requests: int,
    window_seconds: int
) -> Tuple[bool, int]:
    """
    Check rate limit using in-memory storage.
    
    Returns:
        Tuple[bool, int]: (is_allowed, remaining_requests)
    """
    with _memory_lock:
        current_time = time.time()
        _cleanup_memory_store(current_time)
        storage_key = (key, window_seconds)
        if storage_key not in _memory_store:
            if len(_memory_store) >= MAX_MEMORY_IDENTIFIERS:
                raise RateLimitUnavailable("Rate limit unavailable")
            _memory_store[storage_key] = []
        timestamps = _memory_store[storage_key]
        if len(timestamps) >= max_requests:
            return False, 0
        timestamps.append(current_time)
        return True, max_requests - len(timestamps)


class RateLimiter:
    """
    Rate limiter with Redis backend and in-memory fallback.
    
    Usage:
        limiter = RateLimiter(max_requests=10, window_seconds=60)
        is_allowed, remaining = limiter.check("client_ip")
    """
    
    def __init__(self, max_requests: int, window_seconds: int = 60):
        """
        Initialize rate limiter.
        
        Args:
            max_requests: Maximum number of requests allowed in the window
            window_seconds: Time window in seconds (default: 60)
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._redis_client = None
        self._redis_checked = False
    
    def _get_client(self):
        """Get Redis client, caching the result."""
        if not self._redis_checked:
            self._redis_client = _get_redis_client()
            self._redis_checked = True
        return self._redis_client
    
    def check(self, identifier: str) -> Tuple[bool, int]:
        """
        Check if a request is allowed for the given identifier.
        
        Args:
            identifier: Unique identifier (e.g., IP address)
        
        Returns:
            Tuple[bool, int]: (is_allowed, remaining_requests)
        """
        redis_client = self._get_client()
        
        if redis_client is not None:
            return _check_rate_limit_redis(
                redis_client,
                identifier,
                self.max_requests,
                self.window_seconds
            )
        else:
            return _check_rate_limit_memory(
                identifier,
                self.max_requests,
                self.window_seconds
            )
    
    def reset(self, identifier: str) -> None:
        """
        Reset rate limit for an identifier (mainly for testing).
        
        Args:
            identifier: Unique identifier to reset
        """
        # Reset in-memory store
        with _memory_lock:
            _memory_store.pop((identifier, self.window_seconds), None)
        
        # Reset in Redis if available
        redis_client = self._get_client()
        if redis_client is not None:
            try:
                pattern = f"ratelimit:{identifier}:*"
                keys = redis_client.keys(pattern)
                if keys:
                    redis_client.delete(*keys)
            except Exception:
                pass

