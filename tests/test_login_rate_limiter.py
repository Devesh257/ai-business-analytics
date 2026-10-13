from app.security.login_rate_limiter import (
    LoginRateLimiter,
)


class FakeClock:
    def __init__(self):
        self.value = 1000.0

    def now(self):
        return self.value

    def advance(
        self,
        seconds,
    ):
        self.value += seconds


def test_initial_login_is_allowed():
    clock = FakeClock()

    limiter = LoginRateLimiter(
        now_func=clock.now
    )

    assert (
        limiter.retry_after(
            "user@example.com",
            max_attempts=3,
            window_seconds=60,
        )
        is None
    )


def test_login_is_blocked_after_limit():
    clock = FakeClock()

    limiter = LoginRateLimiter(
        now_func=clock.now
    )

    for _ in range(3):
        limiter.record_failure(
            "user@example.com",
            window_seconds=60,
        )

    assert (
        limiter.retry_after(
            "user@example.com",
            max_attempts=3,
            window_seconds=60,
        )
        == 60
    )


def test_window_expiry_clears_block():
    clock = FakeClock()

    limiter = LoginRateLimiter(
        now_func=clock.now
    )

    for _ in range(3):
        limiter.record_failure(
            "user@example.com",
            window_seconds=60,
        )

    clock.advance(60)

    assert (
        limiter.retry_after(
            "user@example.com",
            max_attempts=3,
            window_seconds=60,
        )
        is None
    )


def test_success_reset_clears_failures():
    clock = FakeClock()

    limiter = LoginRateLimiter(
        now_func=clock.now
    )

    for _ in range(3):
        limiter.record_failure(
            "user@example.com",
            window_seconds=60,
        )

    limiter.reset(
        "user@example.com"
    )

    assert (
        limiter.retry_after(
            "user@example.com",
            max_attempts=3,
            window_seconds=60,
        )
        is None
    )


def test_accounts_are_tracked_separately():
    clock = FakeClock()

    limiter = LoginRateLimiter(
        now_func=clock.now
    )

    for _ in range(3):
        limiter.record_failure(
            "a@example.com",
            window_seconds=60,
        )

    assert (
        limiter.retry_after(
            "a@example.com",
            max_attempts=3,
            window_seconds=60,
        )
        == 60
    )

    assert (
        limiter.retry_after(
            "b@example.com",
            max_attempts=3,
            window_seconds=60,
        )
        is None
    )


def test_retry_after_decreases_with_time():
    clock = FakeClock()

    limiter = LoginRateLimiter(
        now_func=clock.now
    )

    for _ in range(3):
        limiter.record_failure(
            "user@example.com",
            window_seconds=60,
        )

    clock.advance(17)

    assert (
        limiter.retry_after(
            "user@example.com",
            max_attempts=3,
            window_seconds=60,
        )
        == 43
    )
