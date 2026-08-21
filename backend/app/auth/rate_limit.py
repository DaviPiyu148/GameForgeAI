"""
In-memory sliding-window rate limiter for auth and sensitive endpoints.

IMPORTANT SCOPE LIMITATION:
This limiter is single-process only. If multiple Uvicorn workers are deployed,
each worker maintains its own independent window — rate limits are NOT shared
across workers. This is acceptable for hackathon/development deployment.

Redis/distributed rate limiting is deferred to Phase B8.

Protected limits:
  - Login:    10 attempts per IP per 15 minutes
  - Register: 5 attempts per IP per 1 hour
  - Save:     50 saves per user_id per 1 hour
"""
import time
from collections import defaultdict, deque
from threading import Lock
from typing import Deque, Dict


class SlidingWindowRateLimiter:
    """Thread-safe in-memory sliding window rate limiter."""

    def __init__(self) -> None:
        self._windows: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def is_allowed(self, key: str, limit: int, window_seconds: int) -> bool:
        """
        Check if a request identified by `key` is within the allowed rate.

        Args:
            key: Unique identifier (e.g. "login:{ip}", "save:{user_id}")
            limit: Maximum number of requests allowed in the window.
            window_seconds: Length of the sliding window in seconds.

        Returns:
            True if the request is allowed; False if the limit is exceeded.
        """
        now = time.monotonic()
        cutoff = now - window_seconds

        with self._lock:
            window = self._windows[key]
            # Evict entries outside the window
            while window and window[0] < cutoff:
                window.popleft()

            if len(window) >= limit:
                return False

            window.append(now)
            return True

    def clear(self) -> None:
        """Reset all rate limit windows. Used in test suites."""
        with self._lock:
            self._windows.clear()


# Module-level singleton
rate_limiter = SlidingWindowRateLimiter()

# Convenience check functions

def check_login_rate(ip: str) -> bool:
    """10 login attempts per IP per 15 minutes."""
    return rate_limiter.is_allowed(f"login:{ip}", limit=10, window_seconds=900)


def check_register_rate(ip: str) -> bool:
    """5 registration attempts per IP per 1 hour."""
    return rate_limiter.is_allowed(f"register:{ip}", limit=5, window_seconds=3600)


def check_save_rate(user_id: str) -> bool:
    """50 save-discovery requests per user per 1 hour."""
    return rate_limiter.is_allowed(f"save:{user_id}", limit=50, window_seconds=3600)
