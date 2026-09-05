# saas-billing-pipeline

*A tiny SaaS company, a real Stripe API, and the question every founder asks at 2 a.m.: where does the money go?*

This is a data engineering + analytics portfolio project. I built a fake SaaS business inside a Stripe sandbox
(three plans, 200 customers, twelve simulated months of signups, upgrades, cancellations and bouncing credit cards),
then built the pipeline that turns Stripe's billing data into the numbers leadership actually wants:
MRR and its movements, churn and why it happens, cohort retention, lifetime value, and how much revenue leaks
through failed payments.

![CI](https://github.com/mcvelferdomadenik-cloud/saas-billing-pipeline/actions/workflows/ci.yml/badge.svg)
![Daily pipeline](https://github.com/mcvelferdomadenik-cloud/saas-billing-pipeline/actions/workflows/pipeline.yml/badge.svg)

**Status:** the pipeline runs itself. Every push is linted and tested, and every morning GitHub Actions advances the
simulated business by one day and refreshes the warehouse.

## The story in one picture

```
Stripe sandbox  →  Python extractor  →  DuckDB     →  dbt models  →  Jupyter notebook
(fake business,    (incremental sync)   (warehouse)   (staging +      (the answers)
 test clocks)                                          marts)
```

1. **`seed`** creates the business. Stripe *test clocks* let you fast-forward time, so subscriptions really bill,
   renew, upgrade and get cancelled — some customers even get a card that always declines.
2. **`sync`** copies everything out of Stripe, raw. First run is a full backfill; every later run asks
   `/v1/events` "what changed since my cursor?" and fetches only that.
3. **`load`** upserts the raw JSON into DuckDB. Run it a hundred times, get the same tables.
4. **`dbt build`** turns JSON blobs into a proper dimensional model and computes the MRR waterfall.
5. **`analysis.ipynb`** asks the tables the leadership questions and writes down what it found.

## What the data says

- MRR grew from **$429 to $7,050** in a year, almost entirely from new signups — upgrades barely register.
- Monthly churn sits at **2–4%**, except one month at 7.5% when Stripe gave up on a batch of failing cards.
- **A quarter of all churn is accidental**: 10 customers didn't leave, their credit card did. That's ~$4,700 a year
  recoverable with a "please update your card" email.
- Enterprise customers are worth ~$3,600 over their lifetime; Basic monthly is the cheapest *and* the leakiest plan.

The full walk-through with charts is in [`notebooks/analysis.ipynb`](notebooks/analysis.ipynb).

## Setup

1. Create a [Stripe sandbox](https://docs.stripe.com/sandboxes) and put its secret test key in a `.env` file
   in the project root:

   ```
   STRIPE_API_KEY=sk_test_...
   ```

2. Install everything (Python 3.14, managed with [uv](https://docs.astral.sh/uv/)):

   ```
   uv sync
   ```

## Commands

| Command | What it does |
| --- | --- |
| `uv run python -m pipeline.run seed --customers 200` | Seed the sandbox: 3 plans, ~200 customers, 12 months of simulated billing via test clocks |
| `uv run python -m pipeline.run sync` | Extract customers, subscriptions, invoices, charges and events into `data/raw/`. First run is a full backfill; later runs are incremental via `/v1/events` and the cursor in `data/state.json`. Add `--full` to force a backfill. |
| `uv run python -m pipeline.run load` | Load `data/raw/` into DuckDB (`data/warehouse.duckdb`, schema `raw`), upserting by Stripe id so re-runs never duplicate rows |
| `uv run python -m pipeline.run advance` | Move every test clock forward one day (`--days N` for more), so the simulated business keeps billing |
| `cd dbt && uv run dbt build` | Build staging views and marts tables in DuckDB and run all 28 data tests |
| `uv run python -m pytest` | Run the Python tests (fake Stripe API, in-memory DuckDB — no network needed) |
| `uv run python -m ruff check .` | Lint the code |

Everything is idempotent: seeding skips finished cohorts (`data/seed_state.json`), sync resumes from its cursor,
load upserts, dbt rebuilds. If a step crashes halfway, run it again.

## Automation

Two GitHub Actions workflows in `.github/workflows/`:

- **`ci.yml`** runs on every push: ruff, pytest, then `dbt build` against a small committed fixture
  (`tests/fixtures/raw/`, two test clocks' worth of sandbox data) so all 28 data tests run without touching Stripe.
- **`pipeline.yml`** runs every day at 06:00 UTC: `advance` → `sync` → `load` → `dbt build`. The Stripe key lives in a
  repository secret, and `data/` is carried between runs with `actions/cache`, so each day's sync is incremental
  rather than a full backfill.

Stripe deletes sandbox test clocks after ~30 days. When that happens, `seed` and `sync --full` rebuild the business
from scratch — everything downstream is idempotent, so nothing else changes.

## Data model

`dbt/models/staging/` unpacks the raw Stripe JSON into typed views — one per raw table
(`stg_customers`, `stg_subscriptions`, `stg_invoices`, `stg_charges`, `stg_subscription_events`).

`dbt/models/marts/` is where the business logic lives:

| Model | Grain | What it answers |
| --- | --- | --- |
| `dim_plan` | one row per price | plan catalog, with yearly prices normalised to monthly MRR |
| `dim_customer` | one row per customer | cohort month, current plan, lifetime revenue |
| `fct_invoices` | one row per invoice | revenue, unpaid amounts, payment attempts |
| `fct_subscription_events` | one row per start / upgrade / downgrade / cancellation | MRR before and after each change |
| `mrr_customer_monthly` | customer × month | month-end MRR and its movement: new, expansion, contraction, churn, reactivation |
| `mrr_monthly` | one row per month | the MRR waterfall — reconciles to the cent |

## Things I ran into (and what I learned)

- **Test-clock objects are invisible to plain list endpoints.** `/v1/customers` returns nothing; you have to walk
  the test clocks first. `/v1/events`, luckily, sees everything.
- **Row-by-row inserts into DuckDB are slow** (13k events took minutes). Writing a staging file and doing one
  `INSERT … SELECT … ON CONFLICT DO UPDATE` takes 3 seconds.
- **Event timestamps are real time, not simulated time.** For the MRR timeline I had to take the subscription's own
  `current_period_start` from inside the event payload.
- **Money is `decimal`, not `float`.** Otherwise your waterfall is off by $0.0000000002 and the reconciliation test fails.
- The Stripe API moved `invoice.subscription` to `invoice.parent.subscription_details.subscription` and dropped
  `charge.invoice` — the docs you read and the JSON you get are not always the same version.

## Stack

Python 3.14 · uv · requests · DuckDB · dbt-duckdb · pandas · plotly · pytest · ruff
