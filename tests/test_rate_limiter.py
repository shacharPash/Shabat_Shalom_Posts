"""
Unit tests for rate limiter module.

Tests cover:
- Basic rate limiting functionality
- In-memory fallback when Redis is unavailable
- Rate limit reset functionality
- Multiple identifiers isolation
"""

import os
import sys
import time
import unittest
from unittest.mock import patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rate_limiter import RateLimiter, _memory_store


class TestRateLimiterInMemory(unittest.TestCase):
    """Tests for rate limiter using in-memory storage (no Redis)."""

    def setUp(self):
        """Clear memory store before each test."""
        _memory_store.clear()

    @patch('rate_limiter._get_redis_client')
    def test_allows_requests_under_limit(self, mock_redis):
        """Requests under the limit should be allowed."""
        mock_redis.return_value = None  # No Redis
        
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        
        for i in range(5):
            is_allowed, remaining = limiter.check("test_ip")
            self.assertTrue(is_allowed, f"Request {i+1} should be allowed")
            self.assertEqual(remaining, 4 - i)

    @patch('rate_limiter._get_redis_client')
    def test_blocks_requests_over_limit(self, mock_redis):
        """Requests over the limit should be blocked."""
        mock_redis.return_value = None  # No Redis
        
        limiter = RateLimiter(max_requests=3, window_seconds=60)
        
        # First 3 requests should pass
        for i in range(3):
            is_allowed, _ = limiter.check("test_ip")
            self.assertTrue(is_allowed)
        
        # 4th request should be blocked
        is_allowed, remaining = limiter.check("test_ip")
        self.assertFalse(is_allowed)
        self.assertEqual(remaining, 0)

    @patch('rate_limiter._get_redis_client')
    def test_different_identifiers_isolated(self, mock_redis):
        """Different identifiers should have separate rate limits."""
        mock_redis.return_value = None  # No Redis
        
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        
        # Use up all requests for ip1
        limiter.check("ip1")
        limiter.check("ip1")
        is_allowed1, _ = limiter.check("ip1")
        
        # ip2 should still have requests available
        is_allowed2, remaining2 = limiter.check("ip2")
        
        self.assertFalse(is_allowed1, "ip1 should be rate limited")
        self.assertTrue(is_allowed2, "ip2 should not be rate limited")
        self.assertEqual(remaining2, 1)

    @patch('rate_limiter._get_redis_client')
    def test_reset_clears_limit(self, mock_redis):
        """Reset should clear the rate limit for an identifier."""
        mock_redis.return_value = None  # No Redis
        
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        
        # Use up all requests
        limiter.check("test_ip")
        limiter.check("test_ip")
        
        # Should be blocked
        is_allowed, _ = limiter.check("test_ip")
        self.assertFalse(is_allowed)
        
        # Reset
        limiter.reset("test_ip")
        
        # Should be allowed again
        is_allowed, remaining = limiter.check("test_ip")
        self.assertTrue(is_allowed)
        self.assertEqual(remaining, 1)

    @patch('rate_limiter._get_redis_client')
    @patch('rate_limiter.time.time')
    def test_window_expiration(self, mock_time, mock_redis):
        """Rate limit should reset after window expires."""
        mock_redis.return_value = None  # No Redis
        
        # Start at time 1000
        mock_time.return_value = 1000.0
        
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        
        # Use up all requests
        limiter.check("test_ip")
        limiter.check("test_ip")
        
        # Should be blocked
        is_allowed, _ = limiter.check("test_ip")
        self.assertFalse(is_allowed)
        
        # Move time forward past the window
        mock_time.return_value = 1061.0
        
        # Should be allowed again
        is_allowed, remaining = limiter.check("test_ip")
        self.assertTrue(is_allowed)
        self.assertEqual(remaining, 1)


class TestRateLimiterWithRedis(unittest.TestCase):
    """Tests for rate limiter using Redis."""

    @patch('rate_limiter._get_redis_client')
    def test_uses_redis_when_available(self, mock_get_redis):
        """Rate limiter should use Redis when available."""
        mock_redis = MagicMock()
        mock_pipe = MagicMock()
        mock_pipe.execute.return_value = [1, True]  # count=1, expire=True
        mock_redis.pipeline.return_value = mock_pipe
        mock_get_redis.return_value = mock_redis
        
        limiter = RateLimiter(max_requests=10, window_seconds=60)
        is_allowed, remaining = limiter.check("test_ip")
        
        self.assertTrue(is_allowed)
        self.assertEqual(remaining, 9)
        mock_pipe.incr.assert_called_once()
        mock_pipe.expire.assert_called_once()

    @patch('rate_limiter._get_redis_client')
    def test_redis_blocks_over_limit(self, mock_get_redis):
        """Redis should block requests over the limit."""
        mock_redis = MagicMock()
        mock_pipe = MagicMock()
        mock_pipe.execute.return_value = [11, True]  # count=11 (over limit)
        mock_redis.pipeline.return_value = mock_pipe
        mock_get_redis.return_value = mock_redis
        
        limiter = RateLimiter(max_requests=10, window_seconds=60)
        is_allowed, remaining = limiter.check("test_ip")
        
        self.assertFalse(is_allowed)
        self.assertEqual(remaining, 0)


if __name__ == "__main__":
    unittest.main()

