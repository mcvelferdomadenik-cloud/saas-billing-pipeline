"""Sample two test clocks' worth of raw data into tests/fixtures/raw for CI."""

import json
from pathlib import Path

from pipeline.load import latest_snapshots

RAW_DIR = Path("data/raw")
FIXTURE_DIR = Path("tests/fixtures/raw")
CLOCKS_TO_KEEP = 2


def main() -> None:
    customers = latest_snapshots(RAW_DIR / "customers")
    clocks = sorted({c["test_clock"] for c in customers})[:CLOCKS_TO_KEEP]
    customers = [c for c in customers if c["test_clock"] in clocks]
    ids = {c["id"] for c in customers}

    def belongs(obj: dict) -> bool:
        return obj.get("customer") in ids

    fixture = {
        "customers": customers,
        "subscriptions": [s for s in latest_snapshots(RAW_DIR / "subscriptions") if belongs(s)],
        "invoices": [i for i in latest_snapshots(RAW_DIR / "invoices") if belongs(i)],
        "charges": [c for c in latest_snapshots(RAW_DIR / "charges") if belongs(c)],
        "events": [
            e
            for e in latest_snapshots(RAW_DIR / "events")
            if e["type"].startswith("customer.subscription") and belongs(e["data"]["object"])
        ],
    }
    for name, objects in fixture.items():
        path = FIXTURE_DIR / name / "fixture.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(objects))
        print(f"{name}: {len(objects)} objects -> {path}")


if __name__ == "__main__":
    main()
