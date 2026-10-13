from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from threading import Lock
import time


@dataclass
class LoginAttemptState:
    failures: int
    first_failure_at: float


class LoginRateLimiter:
    def __init__(
        self,
        now_func=None,
    ):
        self._now_func = (
            now_func
            or time.monotonic
        )

        self._attempts: dict[
            str,
            LoginAttemptState,
        ] = {}

        self._lock = Lock()


    def _now(self) -> float:
        return float(
            self._now_func()
        )


    def retry_after(
        self,
        key: str,
        *,
        max_attempts: int,
        window_seconds: int,
    ) -> int | None:
        now = self._now()

        with self._lock:
            state = self._attempts.get(
                key
            )

            if state is None:
                return None

            elapsed = (
                now
                - state.first_failure_at
            )

            if (
                elapsed
                >= window_seconds
            ):
                self._attempts.pop(
                    key,
                    None,
                )
                return None

            if (
                state.failures
                < max_attempts
            ):
                return None

            return max(
                1,
                ceil(
                    window_seconds
                    - elapsed
                ),
            )


    def record_failure(
        self,
        key: str,
        *,
        window_seconds: int,
    ) -> None:
        now = self._now()

        with self._lock:
            state = self._attempts.get(
                key
            )

            if state is None:
                self._attempts[key] = (
                    LoginAttemptState(
                        failures=1,
                        first_failure_at=now,
                    )
                )
                return

            elapsed = (
                now
                - state.first_failure_at
            )

            if (
                elapsed
                >= window_seconds
            ):
                self._attempts[key] = (
                    LoginAttemptState(
                        failures=1,
                        first_failure_at=now,
                    )
                )
                return

            state.failures += 1


    def reset(
        self,
        key: str,
    ) -> None:
        with self._lock:
            self._attempts.pop(
                key,
                None,
            )


    def reset_all(self) -> None:
        with self._lock:
            self._attempts.clear()


login_rate_limiter = (
    LoginRateLimiter()
)
