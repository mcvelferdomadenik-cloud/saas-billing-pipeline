"""Extract raw Stripe objects into data/raw/."""

import json
import logging
import time
from datetime import UTC, datetime
from pathlib import Path

import requests

from pipeline.config import get_stripe_api_key

log = logging.getLogger(__name__)

BASE_URL = "https://api.stripe.com/v1"
PAGE_SIZE = 100  # Stripe's max per list request


class StripeClient:
    """Thin Stripe REST client: GET one page, or walk all pages of a list."""

    def __init__(self, api_key: str, session: requests.Session | None = None) -> None:
        self.session = session or requests.Session()
        self.session.headers["Authorization"] = f"Bearer {api_key}"

    def get(self, path: str, params: dict | None = None, retries: int = 5) -> dict:
        """GET a path; retry 429/5xx with exponential backoff (1s, 2s, 4s...)."""
        url = f"{BASE_URL}/{path}"
        for attempt in range(retries + 1):
            response = self.session.get(url, params=params, timeout=30)
            if response.status_code < 400:
                return response.json()
            retryable = response.status_code == 429 or response.status_code >= 500
            if not retryable or attempt == retries:
                response.raise_for_status()
            wait = 2**attempt
            log.warning("%s -> HTTP %s, retrying in %ss", path, response.status_code, wait)
            time.sleep(wait)
        raise AssertionError("unreachable")

    def list_all(self, path: str, params: dict | None = None) -> list[dict]:
        """Follow has_more / starting_after until the whole list is fetched."""
        params = dict(params or {}, limit=PAGE_SIZE)
        objects: list[dict] = []
        while True:
            page = self.get(path, params)
            objects.extend(page["data"])
            if not page["has_more"]:
                return objects
            params["starting_after"] = page["data"][-1]["id"]


RAW_DIR = Path("data/raw")


def sync_timestamp() -> str:
    """Current UTC time, safe for filenames: 2026-09-03T14-05-22Z."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%SZ")


def write_raw(object_type: str, objects: list[dict], sync_ts: str) -> Path:
    """Write one JSON file per object type per sync run and return its path."""
    path = RAW_DIR / object_type / f"{sync_ts}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(objects, indent=2))
    log.info("wrote %d %s -> %s", len(objects), object_type, path)
    return path


def backfill(client: StripeClient) -> dict[str, list[dict]]:
    """Fetch every customer, subscription, invoice and charge.

    Test-clock objects are hidden from plain list endpoints, so we walk the
    test clocks first, then the customers on each clock.
    """
    clocks = client.list_all("test_helpers/test_clocks")
    log.info("backfill: %d test clocks", len(clocks))

    customers: list[dict] = []
    subscriptions: list[dict] = []
    for clock in clocks:
        customers += client.list_all("customers", {"test_clock": clock["id"]})
        subscriptions += client.list_all(
            "subscriptions", {"test_clock": clock["id"], "status": "all"}
        )

    invoices: list[dict] = []
    charges: list[dict] = []
    for customer in customers:
        invoices += client.list_all("invoices", {"customer": customer["id"]})
        charges += client.list_all("charges", {"customer": customer["id"]})

    events = client.list_all("events")
    events.reverse()

    return {
        "customers": customers,
        "subscriptions": subscriptions,
        "invoices": invoices,
        "charges": charges,
        "events": events,
    }


STATE_FILE = Path("data/state.json")

OBJECT_TYPES = {
    "customer": "customers",
    "subscription": "subscriptions",
    "invoice": "invoices",
    "charge": "charges",
}


def load_state() -> dict:
    """Read the sync cursor; an empty dict means 'never synced'."""
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def incremental(client: StripeClient, since: int) -> dict[str, list[dict]]:
    """Fetch events since the cursor and unpack the object snapshot each one carries."""
    events = client.list_all("events", {"created[gte]": since})
    events.reverse()  # Stripe returns newest first; we want chronological order
    log.info("incremental: %d events since %s", len(events), since)

    result: dict[str, list[dict]] = {"events": events}
    for event in events:
        obj = event["data"]["object"]
        folder = OBJECT_TYPES.get(obj.get("object"))
        if folder:
            result.setdefault(folder, []).append(obj)
    return result


def sync(full: bool = False) -> None:
    """Backfill on first run (or --full); otherwise incremental from the saved cursor."""
    client = StripeClient(get_stripe_api_key())
    state = load_state()
    ts = sync_timestamp()
    started = int(time.time())

    if full or "cursor" not in state:
        data = backfill(client)
        cursor = started
    else:
        data = incremental(client, state["cursor"])
        cursor = max((e["created"] for e in data["events"]), default=state["cursor"])

    for object_type, objects in data.items():
        write_raw(object_type, objects, ts)
    save_state({"cursor": cursor, "last_sync": ts})
    log.info("sync complete, cursor=%s", cursor)
