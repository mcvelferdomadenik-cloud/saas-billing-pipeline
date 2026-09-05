"""Advance every Stripe test clock so the simulated business keeps billing."""

import logging
import time

import stripe

from pipeline.config import get_stripe_api_key

log = logging.getLogger(__name__)

DAY = 24 * 60 * 60


def wait_until_ready(clock_id: str, timeout: int = 300) -> None:
    """Advancing is asynchronous on Stripe's side; poll until the clock settles."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        clock = stripe.test_helpers.TestClock.retrieve(clock_id)
        if clock.status == "ready":
            return
        if clock.status == "internal_failure":
            raise RuntimeError(f"test clock {clock_id} failed on Stripe's side")
        time.sleep(2)
    raise TimeoutError(f"test clock {clock_id} still advancing after {timeout}s")


def advance(clock_id: str, frozen_time: int, retries: int = 5) -> None:
    """Advance one clock, backing off when Stripe rate-limits us (1s, 2s, 4s...)."""
    for attempt in range(retries + 1):
        try:
            stripe.test_helpers.TestClock.advance(clock_id, frozen_time=frozen_time)
            return
        except stripe.RateLimitError:
            if attempt == retries:
                raise
            time.sleep(2**attempt)


def advance_all(days: int = 1) -> int:
    """Move every ready test clock forward by `days`; return how many were advanced."""
    stripe.api_key = get_stripe_api_key()
    clocks = [
        c
        for c in stripe.test_helpers.TestClock.list(limit=100).auto_paging_iter()
        if c.status == "ready"
    ]
    for clock in clocks:
        advance(clock.id, clock.frozen_time + days * DAY)
    for clock in clocks:
        wait_until_ready(clock.id)
    log.info("advanced %d test clocks by %d day(s)", len(clocks), days)
    return len(clocks)
