# saas-billing-pipeline

Data engineering portfolio project: a simulated SaaS business runs on Stripe,
and this pipeline turns its billing data into revenue analytics — MRR
movements, churn, cohort retention, and failed-payment losses.

**Status: work in progress.** Phases 1–4 (seed, extraction, DuckDB load, dbt models) are done; analysis and CI are in progress.

## Architecture

```
Stripe sandbox  →  Python extractor  →  DuckDB     →  dbt models  →  notebooks
(fake business,    (incremental sync)   (warehouse)   (staging +      (analysis)
 test clocks)                                          marts)
```

## Setup

1. Create a [Stripe sandbox](https://docs.stripe.com/sandboxes) and put its
   secret test key in a `.env` file in the project root:

   ```
   STRIPE_API_KEY=sk_test_...
   ```

2. Install dependencies:

   ```
   uv sync
   ```

## Commands

| Command | What it does |
| --- | --- |
| `uv run python -m pipeline.run seed --customers 200` | Seed the sandbox: 3 plans, ~200 customers, 12 months of simulated billing via test clocks |
| `uv run python -m pipeline.run sync` | Extract customers, subscriptions, invoices, charges and events into `data/raw/`. First run is a full backfill; later runs are incremental via `/v1/events` and the cursor in `data/state.json`. Add `--full` to force a backfill. |
| `uv run python -m pipeline.run load` | Load `data/raw/` into DuckDB (`data/warehouse.duckdb`, schema `raw`), upserting by Stripe id so re-runs never duplicate rows |
| `uv run python -m pytest` | Run the tests |
| `uv run python -m ruff check .` | Lint the code |
| `cd dbt && uv run dbt build` | Build staging views and marts tables in DuckDB and run all data tests |

Seeding is idempotent and resumable: re-running skips finished work
(`data/seed_state.json` tracks progress), and the same `--seed` always
generates the same business.

## Data model

`dbt/models/staging/` unpacks the raw Stripe JSON into typed views (`stg_customers`, `stg_subscriptions`, `stg_invoices`, `stg_charges`, `stg_subscription_events`).

`dbt/models/marts/` holds the business logic:

| Model | Grain | What it answers |
| --- | --- | --- |
| `dim_plan` | one row per price | plan catalog with MRR-normalised amounts |
| `dim_customer` | one row per customer | cohort month, current plan, lifetime revenue |
| `fct_invoices` | one row per invoice | revenue, unpaid amounts, payment attempts |
| `fct_subscription_events` | one row per start / upgrade / downgrade / cancellation | MRR before and after each change |
| `mrr_customer_monthly` | customer × month | month-end MRR and movement (new, expansion, contraction, churn, reactivation) |
| `mrr_monthly` | one row per month | the MRR waterfall |