"""
Gemini Credential Health Registry.

Tracks per-credential health in-memory to enable sequential failover without
proactive rotation.  Health state is process-local and resets on restart.

Security invariants:
- Raw API key strings are NEVER written to logs, stored in the database, or
  returned from any API endpoint.
- Only a masked identifier (last 4 characters) is used for observability.
- The registry receives an ordered, deduplicated key pool at startup and
  exposes integer indices (not the key values themselves) to callers.
"""
import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from app.ai.provider import ProviderErrorClass
from app.config import settings

log = logging.getLogger(__name__)


def _mask_key(raw_key: str) -> str:
    """Return a safe display identifier.  Never exposes the full key."""
    if not raw_key or len(raw_key) < 4:
        return "****"
    return f"...{raw_key[-4:]}"


@dataclass
class ProviderKeyState:
    """In-memory health record for a single configured credential."""
    key_index: int                            # Ordinal position in the configured pool (0-based)
    masked_key: str                           # Safe display identifier; never the real key
    consecutive_failures: int = 0
    disabled_until: Optional[datetime] = None
    last_success_at: Optional[datetime] = None
    last_failure_at: Optional[datetime] = None
    last_error_class: Optional[ProviderErrorClass] = None

    def is_in_cooldown(self, now: Optional[datetime] = None) -> bool:
        if self.disabled_until is None:
            return False
        return (now or datetime.now(timezone.utc)) < self.disabled_until

    def is_eligible(self, now: Optional[datetime] = None) -> bool:
        return not self.is_in_cooldown(now)


class GeminiKeyRegistry:
    """
    In-memory registry for all configured Gemini credentials.

    Semantics:
    - Credentials are always tried in their configured order.
    - A credential that is healthy is tried first and kept first (no round-robin).
    - A credential in cooldown is skipped but not permanently removed.
    - Cooldown is cleared automatically when the cooldown duration expires.
    - Duplicate keys are removed at startup; configured order is preserved.
    """

    def __init__(
        self,
        api_keys: Optional[List[str]] = None,
        failure_threshold: Optional[int] = None,
        cooldown_seconds: Optional[float] = None,
    ):
        raw_pool: List[str] = api_keys if api_keys is not None else settings.gemini_api_key_pool()
        self._failure_threshold: int = (
            failure_threshold
            if failure_threshold is not None
            else settings.KEY_FAILURE_THRESHOLD
        )
        self._cooldown_seconds: float = (
            cooldown_seconds
            if cooldown_seconds is not None
            else float(settings.KEY_COOLDOWN_SECONDS)
        )
        # Build ordered, deduplicated key list
        self._keys: List[str] = []
        seen: set = set()
        for k in raw_pool:
            k = (k or "").strip()
            if k and k not in seen:
                seen.add(k)
                self._keys.append(k)

        if len(self._keys) < len(raw_pool):
            log.warning(
                "[AI] Credential pool had %d duplicate(s); deduplicated to %d unique credentials.",
                len(raw_pool) - len(self._keys),
                len(self._keys),
            )
        if len(raw_pool) > 1:
            log.info(
                "[AI] Credential pool initialized with %d credential(s). "
                "Note: quota independence depends on each credential belonging to a "
                "separate Google API project. Multiple credentials from the same project "
                "share project-level quota.",
                len(self._keys),
            )

        self._states: Dict[int, ProviderKeyState] = {
            i: ProviderKeyState(key_index=i, masked_key=_mask_key(k))
            for i, k in enumerate(self._keys)
        }
        self._lock = asyncio.Lock()

    # ── Public API ────────────────────────────────────────────────────────

    @property
    def pool_size(self) -> int:
        return len(self._keys)

    def get_key(self, idx: int) -> Optional[str]:
        """Return the raw key for the given index. Never log or expose this value."""
        return self._keys[idx] if 0 <= idx < len(self._keys) else None

    def get_eligible_keys(self) -> List[Tuple[int, str]]:
        """
        Return (index, raw_key) pairs in configured order, skipping credentials in cooldown.

        Callers iterate this list and try each credential sequentially, stopping on the
        first success.  Keys NOT in cooldown appear first in their original order; keys in
        cooldown are filtered out entirely for this request cycle.
        """
        now = datetime.now(timezone.utc)
        eligible: List[Tuple[int, str]] = []
        for i, key in enumerate(self._keys):
            state = self._states[i]
            if state.is_eligible(now):
                eligible.append((i, key))
        return eligible

    async def record_success(self, key_index: int) -> None:
        """Reset health state for a credential after a successful request."""
        async with self._lock:
            state = self._states.get(key_index)
            if state is None:
                return
            was_in_cooldown = state.disabled_until is not None
            state.consecutive_failures = 0
            state.disabled_until = None
            state.last_success_at = datetime.now(timezone.utc)
            state.last_error_class = None
        if was_in_cooldown:
            log.info("[AI] KEY #%d (%s): recovered from cooldown.", key_index + 1, state.masked_key)

    async def record_failure(
        self, key_index: int, error_class: ProviderErrorClass
    ) -> None:
        """
        Record a credential failure and apply cooldown policy.

        Policy:
        - KEY_AUTH_FAILURE (401/403): immediate cooldown — the credential is explicitly
          rejected; retrying it sooner is pointless and wasteful.
        - RATE_LIMIT (429): incremental — may be per-minute RPM limit; enters cooldown
          after threshold to avoid hammering the same project.
        - TRANSIENT_PROVIDER / NETWORK_ERROR / UNKNOWN: incremental — transient errors
          should not permanently punish a healthy credential.
        - Other classes (INVALID_REQUEST, CONTENT_SAFETY, SCHEMA_PARSING): these are
          NOT credential failures; the registry should not be called for these.
        """
        async with self._lock:
            state = self._states.get(key_index)
            if state is None:
                return
            state.last_failure_at = datetime.now(timezone.utc)
            state.last_error_class = error_class

            if error_class == ProviderErrorClass.KEY_AUTH_FAILURE:
                # Credential explicitly rejected — immediate cooldown (restart will clear)
                state.consecutive_failures = self._failure_threshold
                state.disabled_until = datetime.now(timezone.utc) + timedelta(seconds=self._cooldown_seconds)
                log.warning(
                    "[AI] KEY #%d (%s): authentication failure — entering cooldown for %.0fs.",
                    key_index + 1, state.masked_key, self._cooldown_seconds,
                )
            else:
                state.consecutive_failures += 1
                if state.consecutive_failures >= self._failure_threshold:
                    state.disabled_until = datetime.now(timezone.utc) + timedelta(seconds=self._cooldown_seconds)
                    log.warning(
                        "[AI] KEY #%d (%s): %d consecutive %s failures — entering cooldown for %.0fs.",
                        key_index + 1, state.masked_key,
                        state.consecutive_failures, error_class.value,
                        self._cooldown_seconds,
                    )
                else:
                    log.info(
                        "[AI] KEY #%d (%s): %s failure (%d/%d before cooldown).",
                        key_index + 1, state.masked_key,
                        error_class.value, state.consecutive_failures,
                        self._failure_threshold,
                    )

    def get_state(self, key_index: int) -> Optional[ProviderKeyState]:
        """Return a snapshot of credential health state (safe for logging/debugging)."""
        return self._states.get(key_index)

    def __len__(self) -> int:
        return len(self._keys)

    def __bool__(self) -> bool:
        return bool(self._keys)


# ── Singleton ─────────────────────────────────────────────────────────────
# Initialized once at import time; process-local; resets on restart.
gemini_key_registry = GeminiKeyRegistry()
