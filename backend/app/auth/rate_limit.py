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
from collections import OrderedDict, deque
from threading import Lock
from typing import Deque, Optional


class SlidingWindowRateLimiter:
    """Thread-safe in-memory sliding window rate limiter with LRU eviction and memory bounds."""

    def __init__(self, max_keys: int = 10_000, default_max_window: int = 3600) -> None:
        self._max_keys = max_keys
        self._default_max_window = default_max_window
        self._windows: OrderedDict[str, Deque[float]] = OrderedDict()
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
            window = self._windows.get(key)
            if window is not None:
                # Evict entries outside the sliding window
                while window and window[0] < cutoff:
                    window.popleft()

                if not window:
                    # All prior timestamps have expired — prune the empty deque
                    del self._windows[key]
                    window = None

            if window is not None and len(window) >= limit:
                # Update LRU ordering even on reject
                self._windows.move_to_end(key)
                return False

            if window is None:
                # If at capacity, prune before allocating new key
                if len(self._windows) >= self._max_keys:
                    self._prune(now)

                window = deque()
                self._windows[key] = window
            else:
                self._windows.move_to_end(key)

            window.append(now)

            # Defensive post-insertion guard: guarantees strict upper memory bound
            while len(self._windows) > self._max_keys:
                self._windows.popitem(last=False)

            return True

    def _prune(self, now: float) -> None:
        """
        Evict expired entries and enforce capacity cap.
        Must be called while holding self._lock.
        """
        cutoff = now - self._default_max_window
        keys_to_remove = []

        # Pass 1: Prune keys that are empty or have completely expired timestamps
        for k, w in self._windows.items():
            while w and w[0] < cutoff:
                w.popleft()
            if not w:
                keys_to_remove.append(k)

        for k in keys_to_remove:
            del self._windows[k]

        # Pass 2: If still at or above capacity, drop oldest LRU items from the front
        while len(self._windows) >= self._max_keys:
            self._windows.popitem(last=False)

    def prune_expired(self, max_age_seconds: Optional[int] = None) -> int:
        """
        Explicitly sweep and prune keys whose timestamps have all expired.
        Useful for scheduled background maintenance and testing.

        Args:
            max_age_seconds: Optional expiration threshold in seconds.
                If None, defaults to `self._default_max_window` (default: 3600 seconds).
                Any key whose entries are strictly older than (now - max_age_seconds)
                or empty is purged from memory.

        Returns:
            int: The exact count of dictionary keys (clients) removed from memory
                (not individual timestamps).
        """
        now = time.monotonic()
        window_sec = max_age_seconds if max_age_seconds is not None else self._default_max_window
        cutoff = now - window_sec
        pruned = 0

        with self._lock:
            keys_to_remove = []
            for k, w in self._windows.items():
                while w and w[0] < cutoff:
                    w.popleft()
                if not w:
                    keys_to_remove.append(k)

            for k in keys_to_remove:
                del self._windows[k]
                pruned += 1

        return pruned

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


def check_preference_mutate_rate(user_id: str) -> bool:
    """
    20 Game DNA preference mutation operations (reset and onboard) per user per 1 hour.

    Shares the cache key 'preference_mutate:{user_id}' across both
    POST /api/profile/preferences/reset and POST /api/profile/preferences/onboard.

    IMPORTANT SCOPE LIMITATION:
    This rate limiter operates in-memory and is local to the current application worker process.
    Under single-worker operation (ADR-004), in-memory window tracking is consistent.
    Distributed rate limiting (e.g. via Redis) is deferred until horizontal scaling.
    """
    return rate_limiter.is_allowed(f"preference_mutate:{user_id}", limit=20, window_seconds=3600)

