"""Export dashboard-ready aggregates from the dbt marts to docs/data.json."""

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

import duckdb

log = logging.getLogger(__name__)

DB_PATH = Path("data/warehouse.duckdb")
OUT_PATH = Path("docs/data.json")

MRR_SQL = """
    select month::varchar as month, mrr, active_customers, new_mrr, expansion_mrr,
           reactivation_mrr, contraction_mrr, churn_mrr, new_customers, churned_customers
    from marts.mrr_monthly order by month
"""
PLANS_SQL = """
    select current_plan_key as plan,
           count(*) filter (where subscription_status = 'active') as active,
           count(*) filter (where subscription_status = 'canceled') as canceled,
           count(*) filter (where cancellation_reason = 'cancellation_requested') as cancellation_requested,
           count(*) filter (where cancellation_reason = 'payment_failed') as payment_failed
    from marts.dim_customer group by 1 order by 1
"""
COHORTS_SQL = """
    select strftime(c.cohort_month, '%Y-%m') as cohort,
           (year(m.month) - year(c.cohort_month)) * 12 + (month(m.month) - month(c.cohort_month)) as months_since,
           round(avg(case when m.mrr > 0 then 1 else 0 end), 2) as retained
    from marts.mrr_customer_monthly m join marts.dim_customer c using (customer_id)
    where m.month >= c.cohort_month group by 1, 2 order by 1, 2
"""
UNPAID_SQL = "select coalesce(sum(amount_unpaid), 0) from marts.fct_invoices where not is_paid"


def export(db_path: Path = DB_PATH, out_path: Path = OUT_PATH) -> None:
    """Query the marts and write one JSON file the static dashboard can fetch."""
    with duckdb.connect(str(db_path), read_only=True) as con:
        rows = lambda sql: con.sql(sql).df().to_dict(orient="records")  # noqa: E731
        payload = {
            "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "mrr_monthly": rows(MRR_SQL),
            "plans": rows(PLANS_SQL),
            "cohorts": rows(COHORTS_SQL),
            "unpaid_amount": float(con.sql(UNPAID_SQL).fetchone()[0]),
        }
    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text(json.dumps(payload, default=float))
    log.info("wrote %s (%d months, %d plans)", out_path, len(payload["mrr_monthly"]), len(payload["plans"]))