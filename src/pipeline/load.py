"""Load raw JSON snapshots from data/raw/ into DuckDB, upserting by Stripe id."""

import json
import logging
import tempfile
from pathlib import Path

import duckdb

log = logging.getLogger(__name__)

RAW_DIR = Path("data/raw")
DB_PATH = Path("data/warehouse.duckdb")


def latest_snapshots(folder: Path) -> list[dict]:
    """Read every JSON file in timestamp order; the last snapshot of each id wins."""
    latest: dict[str, dict] = {}
    for path in sorted(folder.glob("*.json")):
        for obj in json.loads(path.read_text()):
            latest[obj["id"]] = obj
    return list(latest.values())


def upsert(con: duckdb.DuckDBPyConnection, table: str, objects: list[dict]) -> None:
    """Insert new objects into raw.<table>, update existing ones (matched by id)."""
    con.execute(f"""
        CREATE TABLE IF NOT EXISTS raw.{table} (
            id VARCHAR PRIMARY KEY,
            data JSON,
            loaded_at TIMESTAMP
        )
    """)
    with tempfile.TemporaryDirectory() as tmp:
        staging = Path(tmp) / f"{table}.json"
        staging.write_text(json.dumps(objects))
        con.execute(
            f"""
            INSERT INTO raw.{table}
            SELECT json->>'$.id', json, now()
            FROM read_json(?, format='array', records=false)
            ON CONFLICT (id) DO UPDATE SET data = excluded.data, loaded_at = excluded.loaded_at
            """,
            [str(staging)],
        )


def load(db_path: Path = DB_PATH) -> None:
    """Load every object folder under data/raw/ into the warehouse."""
    con = duckdb.connect(str(db_path))
    con.execute("CREATE SCHEMA IF NOT EXISTS raw")
    for folder in sorted(p for p in RAW_DIR.iterdir() if p.is_dir()):
        objects = latest_snapshots(folder)
        upsert(con, folder.name, objects)
        total = con.execute(f"SELECT count(*) FROM raw.{folder.name}").fetchone()[0]
        log.info("raw.%s: upserted %d objects, table now %d rows", folder.name, len(objects), total)
    con.close()
