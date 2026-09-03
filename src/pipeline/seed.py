"""Seed the Stripe sandbox with a fake SaaS business."""

import json
import time
from datetime import UTC, date, datetime
from pathlib import Path

import stripe

from pipeline.config import get_stripe_api_key
from pipeline.customers import (
    DOWNGRADE_PATH,
    MONTHS,
    UPGRADE_PATH,
    CustomerProfile,
    generate_customers,
)

# Plan catalog. Amounts in cents
PLANS = [
    {"id": "basic", "name": "Basic", "monthly": 1900, "yearly": 19000},
    {"id": "pro", "name": "Pro", "monthly": 4900, "yearly": 49000},
    {"id": "enterprise", "name": "Enterprise", "monthly": 9900, "yearly": 99000},
]

# Stripe test payment methods: first always charges fine,
# second attaches fine but every charge fails.
GOOD_CARD = "pm_card_visa"
FAILING_CARD = "pm_card_chargeCustomerFail"

COHORT_SIZE = 3  # Stripe limit: max 3 customers per test clock
STATE_FILE = Path("data/seed_state.json")


# plan catalog


def ensure_product(plan: dict) -> None:
    """Create the product unless it already exists."""
    try:
        stripe.Product.retrieve(plan["id"])
        print(f"product {plan['id']}: already exists")
    except stripe.InvalidRequestError:
        stripe.Product.create(id=plan["id"], name=plan["name"])
        print(f"product {plan['id']}: created")


def ensure_price(plan: dict, lookup_key: str, interval: str, amount: int) -> None:
    """Create the price unless one with this lookup_key already exists."""
    existing = stripe.Price.list(lookup_keys=[lookup_key], limit=1)
    if existing.data:
        print(f"price {lookup_key}: already exists")
        return
    stripe.Price.create(
        product=plan["id"],
        lookup_key=lookup_key,
        unit_amount=amount,
        currency="usd",
        recurring={"interval": interval},
        nickname=f"{plan['name']} {interval}ly",
    )
    print(f"price {lookup_key}: created")


def get_price_ids() -> dict[str, str]:
    """Map lookup_key ('pro_monthly') -> Stripe price id ('price_...')."""
    keys = [f"{p['id']}_{s}" for p in PLANS for s in ("monthly", "yearly")]
    found = stripe.Price.list(lookup_keys=keys, limit=len(keys))
    return {price.lookup_key: price.id for price in found.data}


def price_key(plan_id: str, interval: str) -> str:
    return f"{plan_id}_monthly" if interval == "month" else f"{plan_id}_yearly"


#  time


def month_start(month: int) -> int:
    """Unix timestamp of the first day of simulation month `month` (UTC).

    Month 0 = first day of the calendar month MONTHS months ago;
    month MONTHS = first day of the current month (end of simulation).
    """
    today = date.today()
    total = today.year * 12 + (today.month - 1) - (MONTHS - month)
    year, mon = divmod(total, 12)
    return int(datetime(year, mon + 1, 1, tzinfo=UTC).timestamp())


# resumability


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"completed": []}


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


# test clocks
def wait_until_ready(clock_id: str, timeout: int = 300) -> None:
    """Advancing is async on Stripe's side — poll until it finishes."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        clock = stripe.test_helpers.TestClock.retrieve(clock_id)
        if clock.status == "ready":
            return
        if clock.status == "internal_failure":
            raise RuntimeError(f"test clock {clock_id} failed on Stripe's side")
        time.sleep(2)
    raise TimeoutError(f"test clock {clock_id} still advancing after {timeout}s")


def advance_to(clock_id: str, ts: int) -> None:
    stripe.test_helpers.TestClock.advance(clock_id, frozen_time=ts)
    wait_until_ready(clock_id)


def delete_clock_if_exists(name: str) -> None:
    """A half-finished cohort from a crashed run is wiped and redone."""
    for clock in stripe.test_helpers.TestClock.list(limit=100).auto_paging_iter():
        if clock.name == name:
            stripe.test_helpers.TestClock.delete(clock.id)
            return


# the executor


def seed_cohort(name: str, cohort: list[CustomerProfile], prices: dict[str, str]) -> None:
    """Act out the scripted life of up to 3 customers on one test clock."""
    signup = cohort[0].signup_month
    delete_clock_if_exists(name)
    clock = stripe.test_helpers.TestClock.create(frozen_time=month_start(signup), name=name)

    subs: dict[int, tuple[str, str]] = {}  # profile.index -> (customer_id, sub_id)
    for p in cohort:
        customer = stripe.Customer.create(name=p.name, email=p.email, test_clock=clock.id)
        pm = stripe.PaymentMethod.attach(GOOD_CARD, customer=customer.id)
        stripe.Customer.modify(customer.id, invoice_settings={"default_payment_method": pm.id})
        sub = stripe.Subscription.create(
            customer=customer.id,
            items=[{"price": prices[price_key(p.plan_id, p.interval)]}],
        )
        subs[p.index] = (customer.id, sub.id)

    # Walk time forward one month at a time, acting out each profile's script.
    for month in range(signup + 1, MONTHS + 1):
        advance_to(clock.id, month_start(month))
        for p in cohort:
            customer_id, sub_id = subs[p.index]
            try:
                if p.failing_card and month == signup + 1:
                    # card "expires": swap the default to one that always fails
                    pm = stripe.PaymentMethod.attach(FAILING_CARD, customer=customer_id)
                    stripe.Customer.modify(
                        customer_id, invoice_settings={"default_payment_method": pm.id}
                    )
                if p.event and p.event_month == month:
                    if p.event == "cancel":
                        stripe.Subscription.cancel(sub_id)
                    else:
                        path = UPGRADE_PATH if p.event == "upgrade" else DOWNGRADE_PATH
                        target = path[p.plan_id]
                        sub = stripe.Subscription.retrieve(sub_id)
                        stripe.Subscription.modify(
                            sub_id,
                            items=[
                                {
                                    "id": sub["items"]["data"][0].id,
                                    "price": prices[price_key(target, p.interval)],
                                }
                            ],
                            proration_behavior="none",
                        )
            except stripe.InvalidRequestError as e:
                # e.g. sub already auto-canceled after failed payments — log, move on
                print(f"  warning: {p.email} month {month}: {e.user_message}")

    # nudge past that so the last month's invoices complete.
    advance_to(clock.id, month_start(MONTHS) + 2 * 3600)


def seed_customers(count: int, seed: int) -> None:
    prices = get_price_ids()
    profiles = generate_customers(count, seed=seed)
    state = load_state()

    # group by signup month, then chunk into clock-sized cohorts of 3
    by_month: dict[int, list[CustomerProfile]] = {}
    for p in profiles:
        by_month.setdefault(p.signup_month, []).append(p)

    cohorts = []
    for month in sorted(by_month):
        group = by_month[month]
        for chunk_no, i in enumerate(range(0, len(group), COHORT_SIZE)):
            cohorts.append((f"seed{seed}-m{month:02d}-c{chunk_no}", group[i : i + COHORT_SIZE]))

    for n, (name, cohort) in enumerate(cohorts, start=1):
        if name in state["completed"]:
            print(f"[{n}/{len(cohorts)}] {name}: already done")
            continue
        print(
            f"[{n}/{len(cohorts)}] {name}: {len(cohort)} customers, "
            f"signup month {cohort[0].signup_month}"
        )
        seed_cohort(name, cohort, prices)
        state["completed"].append(name)
        save_state(state)
    print("seeding complete")


def run(count: int = 200, seed: int = 42) -> None:
    stripe.api_key = get_stripe_api_key()
    for plan in PLANS:
        ensure_product(plan)
        ensure_price(plan, f"{plan['id']}_monthly", "month", plan["monthly"])
        ensure_price(plan, f"{plan['id']}_yearly", "year", plan["yearly"])
    print("plan catalog ready")
    seed_customers(count, seed)
