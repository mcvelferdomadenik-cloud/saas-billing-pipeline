"""Tests for clocks.py against a fake Stripe SDK."""

from types import SimpleNamespace

from pipeline import clocks


def test_advance_all_moves_ready_clocks_by_one_day(monkeypatch):
    fake_clocks = [
        SimpleNamespace(id="clock_1", status="ready", frozen_time=1_000_000),
        SimpleNamespace(id="clock_2", status="advancing", frozen_time=1_000_000),
    ]
    advanced: list[tuple[str, int]] = []

    monkeypatch.setattr(clocks, "get_stripe_api_key", lambda: "sk_test_x")
    monkeypatch.setattr(
        clocks.stripe.test_helpers.TestClock,
        "list",
        lambda **kw: SimpleNamespace(auto_paging_iter=lambda: iter(fake_clocks)),
    )
    monkeypatch.setattr(
        clocks.stripe.test_helpers.TestClock,
        "advance",
        lambda clock_id, frozen_time: advanced.append((clock_id, frozen_time)),
    )
    monkeypatch.setattr(clocks, "wait_until_ready", lambda clock_id: None)

    assert clocks.advance_all(days=1) == 1
    assert advanced == [("clock_1", 1_000_000 + clocks.DAY)]
