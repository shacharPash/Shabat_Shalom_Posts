"""
Rate limiter module with Redis backend and in-memory fallback.

Uses a sliding window counter algorithm for rate limiting.
When Redis is unavailable, falls back to in-memory dictionary.
"""

import os
import time
from typing import Optional, Tuple

# In-memory fallback storage: {key: [(timestamp, count), ...]}
_memory_store: dict = {}


def _get_redis_client():
    """
    Try to get a Redis client. Returns None if Redis is unavailable.
    """
    try:
        from redis_client import get_redis_client
        return get_redis_client()
    except Exception:
        return None


def _cleanup_memory_store(key: str, window_seconds: int) -> None:
    """Remove expired entries from in-memory store."""
    if key not in _memory_store:
        return
    
    current_time = time.time()
    cutoff = current_time - window_seconds
    _memory_store[key] = [
        (ts, count) for ts, count in _memory_store[key]
        if ts > cutoff
    ]


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
        # If Redis fails, allow the request
        return True, max_requests


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
    current_time = time.time()
    
    # Clean up old entries
    _cleanup_memory_store(key, window_seconds)
    
    # Initialize if needed
    if key not in _memory_store:
        _memory_store[key] = []
    
    # Count requests in current window
    cutoff = current_time - window_seconds
    current_count = sum(
        count for ts, count in _memory_store[key]
        if ts > cutoff
    )
    
    if current_count >= max_requests:
        return False, 0
    
    # Add this request
    _memory_store[key].append((current_time, 1))
    remaining = max(0, max_requests - current_count - 1)
    
    return True, remaining


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
        key = identifier
        if key in _memory_store:
            del _memory_store[key]
        
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

