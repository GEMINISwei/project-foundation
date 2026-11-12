import pytest

from shared.errors import AppError
from shared.rate_limit import RateLimiter
from tests.helpers import scalar

pytestmark = pytest.mark.integration


async def test_blocks_after_the_limit_and_says_when_to_retry(db_ready):
    limiter = RateLimiter("test", max_attempts=2, window_seconds=60)
    await limiter.check("key")
    await limiter.check("key")
    with pytest.raises(AppError) as raised:
        await limiter.check("key")
    assert raised.value.spec.status == 429
    assert raised.value.headers is not None
    assert 1 <= int(raised.value.headers["Retry-After"]) <= 60


async def test_keys_and_limiters_are_counted_separately(db_ready):
    first = RateLimiter("first", max_attempts=1, window_seconds=60)
    second = RateLimiter("second", max_attempts=1, window_seconds=60)
    await first.check("a")
    await first.check("b")
    await second.check("a")


async def test_reset_clears_the_count(db_ready):
    limiter = RateLimiter("test", max_attempts=1, window_seconds=60)
    await limiter.check("key")
    await limiter.reset("key")
    await limiter.check("key")


async def test_the_key_is_not_stored_in_plain_text(db_ready):
    await RateLimiter("test", max_attempts=5, window_seconds=60).check("someone@example.com")
    assert await scalar("SELECT count(*) FROM rate_limits WHERE key LIKE '%someone%'") == 0
