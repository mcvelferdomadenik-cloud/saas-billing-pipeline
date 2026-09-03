"""Tests for load.py: last-snapshot-wins and idempotent upserts."""

import json

import duckdb

from pipeline import load


def write(folder, name: str, objects: list[dict]) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{name}.json").write_text(json.dumps(objects))


def test_latest_snapshots_last_file_and_last_row_win(tmp_path):
    write(tmp_path, "2026-01-01T00-00-00Z", [{"id": "in_1", "status": "draft"}])
    write(
        tmp_path,
        "2026-01-02T00-00-00Z",
        [{"id": "in_1", "status": "open"}, {"id": "in_1", "status": "paid"}, {"id": "in_2"}],
    )

    result = load.latest_snapshots(tmp_path)

    assert result == [{"id": "in_1", "status": "paid"}, {"id": "in_2"}]


def test_upsert_is_idempotent_and_updates_existing_rows():
    con = duckdb.connect()
    con.execute("CREATE SCHEMA raw")

    load.upsert(con, "invoices", [{"id": "in_1", "status": "open"}])
    load.upsert(con, "invoices", [{"id": "in_1", "status": "paid"}, {"id": "in_2"}])

    rows = con.execute("SELECT id, data->>'$.status' FROM raw.invoices ORDER BY id").fetchall()
    assert rows == [("in_1", "paid"), ("in_2", None)]


def test_load_reads_every_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(load, "RAW_DIR", tmp_path / "raw")
    write(tmp_path / "raw" / "customers", "2026-01-01T00-00-00Z", [{"id": "cus_1"}])
    write(tmp_path / "raw" / "invoices", "2026-01-01T00-00-00Z", [{"id": "in_1"}, {"id": "in_2"}])
    db = tmp_path / "warehouse.duckdb"

    load.load(db)
    load.load(db)

    con = duckdb.connect(str(db), read_only=True)
    assert con.execute("SELECT count(*) FROM raw.customers").fetchone() == (1,)
    assert con.execute("SELECT count(*) FROM raw.invoices").fetchone() == (2,)
