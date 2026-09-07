"""Dagster definitions: the pipeline as a graph of assets, dbt models included."""

import json
from pathlib import Path

from dagster import (
    AssetCheckResult,
    AssetExecutionContext,
    AssetKey,
    AssetSelection,
    AssetSpec,
    Definitions,
    ScheduleDefinition,
    asset,
    asset_check,
    define_asset_job,
    multi_asset,
)
from dagster_dbt import DbtCliResource, DbtProject, dbt_assets

from pipeline import export, extract, load

DBT_DIR = Path(__file__).resolve().parents[2] / "dbt"
RAW_TABLES = ["customers", "subscriptions", "invoices", "charges", "events"]

dbt_project = DbtProject(project_dir=DBT_DIR, profiles_dir=DBT_DIR)
dbt_project.prepare_if_dev()


@asset
def stripe_raw() -> None:
    """Raw Stripe objects in data/raw/, pulled incrementally via /v1/events."""
    extract.sync()


@multi_asset(specs=[AssetSpec(["raw", t], deps=[stripe_raw]) for t in RAW_TABLES])
def warehouse_raw():
    """raw.* tables in DuckDB, upserted from the latest snapshots."""
    load.load()


@dbt_assets(manifest=dbt_project.manifest_path)
def dbt_models(context: AssetExecutionContext, dbt: DbtCliResource):
    """Staging views, marts, snapshot and tests — one asset per dbt node."""
    yield from dbt.cli(["build"], context=context).stream()


@asset(
    deps=[
        AssetKey("mrr_monthly"),
        AssetKey("mrr_customer_monthly"),
        AssetKey("dim_customer"),
        AssetKey("fct_invoices"),
    ]
)
def dashboard_data() -> None:
    """docs/data.json that feeds the static dashboard."""
    export.export()

@asset_check(asset=dashboard_data)
def dashboard_has_data() -> AssetCheckResult:
    """The exported JSON must carry at least a year of MRR rows and a non-zero latest month."""
    data = json.loads(Path("docs/data.json").read_text())
    months = data["mrr_monthly"]
    latest_mrr = months[-1]["mrr"] if months else 0
    return AssetCheckResult(
        passed=len(months) >= 12 and latest_mrr > 0,
        metadata={"months": len(months), "latest_mrr": latest_mrr},
    )

daily_job = define_asset_job("daily_pipeline", selection=AssetSelection.all())
daily_schedule = ScheduleDefinition(job=daily_job, cron_schedule="0 6 * * *")

defs = Definitions(
    assets=[stripe_raw, warehouse_raw, dbt_models, dashboard_data],
    jobs=[daily_job],
    schedules=[daily_schedule],
    resources={"dbt": DbtCliResource(project_dir=dbt_project)},
    asset_checks=[dashboard_has_data],
)