"""Tests for extract.py against a fake Stripe API (no network)."""

import json

import pytest

from pipeline import extract
from pipeline.extract import StripeClient


class FakeResponse:
    def __init__(self, status_code: int, body: dict | None = None):
        self.status_code = status_code
        self.body = body or {}

    def json(self) -> dict:
        return self.body

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSession:
    """Stands in for requests.Session: replays a scripted list of responses."""

    def __init__(self, responses: list[FakeResponse]):
        self.headers: dict = {}
        self.responses = list(responses)
        self.calls: list[tuple[str, dict]] = []

    def get(self, url: str, params: dict | None = None, timeout: int = 0) -> FakeResponse:
        self.calls.append((url.removeprefix(extract.BASE_URL + "/"), dict(params or {})))
        return self.responses.pop(0)


def page(ids: list[str], has_more: bool) -> FakeResponse:
    return FakeResponse(200, {"data": [{"id": i} for i in ids], "has_more": has_more})


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(extract.time, "sleep", lambda s: None)


def test_auth_header_is_set():
    session = FakeSession([])
    StripeClient("sk_test_abc", session=session)
    assert session.headers["Authorization"] == "Bearer sk_test_abc"


def test_list_all_follows_cursor_across_pages():
    session = FakeSession([page(["a", "b"], True), page(["c"], False)])
    client = StripeClient("sk_test_x", session=session)

    objects = client.list_all("customers")

    assert [o["id"] for o in objects] == ["a", "b", "c"]
    assert session.calls[0][1] == {"limit": 100}
    assert session.calls[1][1] == {"limit": 100, "starting_after": "b"}


def test_get_retries_on_429_then_succeeds():
    session = FakeSession([FakeResponse(429), FakeResponse(500), FakeResponse(200, {"ok": 1})])
    client = StripeClient("sk_test_x", session=session)

    assert client.get("customers") == {"ok": 1}
    assert len(session.calls) == 3


def test_get_does_not_retry_client_errors():
    session = FakeSession([FakeResponse(401)])
    client = StripeClient("sk_test_x", session=session)

    with pytest.raises(RuntimeError, match="401"):
        client.get("customers")
    assert len(session.calls) == 1


def test_incremental_unpacks_snapshots_in_chronological_order():
    events = [
        {"id": "evt_2", "created": 20, "data": {"object": {"object": "invoice", "id": "in_1"}}},
        {"id": "evt_1", "created": 10, "data": {"object": {"object": "customer", "id": "cus_1"}}},
    ]
    session = FakeSession([FakeResponse(200, {"data": events, "has_more": False})])
    client = StripeClient("sk_test_x", session=session)

    result = extract.incremental(client, since=5)

    assert session.calls[0][1]["created[gte]"] == 5
    assert [e["id"] for e in result["events"]] == ["evt_1", "evt_2"]
    assert result["customers"] == [{"object": "customer", "id": "cus_1"}]
    assert result["invoices"] == [{"object": "invoice", "id": "in_1"}]


def test_backfill_walks_clocks_then_customers():
    session = FakeSession(
        [
            page(["clock_1"], False),  # test clocks
            page(["cus_1"], False),  # customers on clock_1
            page(["sub_1"], False),  # subscriptions on clock_1
            page(["in_1"], False),  # invoices of cus_1
            page(["ch_1"], False),  # charges of cus_1
            page(["evt_1"], False),  # events
        ]
    )
    client = StripeClient("sk_test_x", session=session)

    data = extract.backfill(client)

    assert {k: [o["id"] for o in v] for k, v in data.items()} == {
        "customers": ["cus_1"],
        "subscriptions": ["sub_1"],
        "invoices": ["in_1"],
        "charges": ["ch_1"],
        "events": ["evt_1"],
    }
    paths = [call[0] for call in session.calls]
    assert paths == [
        "test_helpers/test_clocks",
        "customers",
        "subscriptions",
        "invoices",
        "charges",
        "events",
    ]
    assert session.calls[2][1]["status"] == "all"


def test_write_raw_and_state_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(extract, "RAW_DIR", tmp_path / "raw")
    monkeypatch.setattr(extract, "STATE_FILE", tmp_path / "state.json")

    path = extract.write_raw("customers", [{"id": "cus_1"}], "2026-01-01T00-00-00Z")
    assert json.loads(path.read_text()) == [{"id": "cus_1"}]
    assert path == tmp_path / "raw" / "customers" / "2026-01-01T00-00-00Z.json"

    assert extract.load_state() == {}
    extract.save_state({"cursor": 42})
    assert extract.load_state() == {"cursor": 42}
