"""Seed the Stripe sandbox with a fake SaaS business."""

import stripe

from pipeline.config import get_stripe_api_key

# Plan catalog. Amounts in cents 
PLANS = [
    {"id": "basic", "name": "Basic", "monthly": 1900, "yearly": 19000},
    {"id": "pro", "name": "Pro", "monthly": 4900, "yearly": 49000},
    {"id": "enterprise", "name": "Enterprise", "monthly": 9900, "yearly": 99000},
]


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


def run() -> None:
    stripe.api_key = get_stripe_api_key()
    for plan in PLANS:
        ensure_product(plan)
        ensure_price(plan, f"{plan['id']}_monthly", "month", plan["monthly"])
        ensure_price(plan, f"{plan['id']}_yearly", "year", plan["yearly"])
    print("plan catalog ready")