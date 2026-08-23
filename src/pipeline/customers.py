"""Generate reproducible fake customer profiles for seeding.

Pure logic — no Stripe calls here. seed.py turns these profiles into
real sandbox objects.
"""

from dataclasses import dataclass
from random import Random

# Simulation window
MONTHS = 12

PLAN_WEIGHTS = {"basic": 0.50, "pro": 0.35, "enterprise": 0.15}
YEARLY_SHARE = 0.30
FAILING_CARD_SHARE = 0.08  # card works at signup, bounces on renewals
CANCEL_SHARE = 0.15
UPGRADE_SHARE = 0.10
DOWNGRADE_SHARE = 0.05

UPGRADE_PATH = {"basic": "pro", "pro": "enterprise"}
DOWNGRADE_PATH = {"pro": "basic", "enterprise": "pro"}

FIRST_NAMES = [
    "Ana",
    "Boris",
    "Clara",
    "David",
    "Eva",
    "Filip",
    "Greta",
    "Hugo",
    "Ivana",
    "Jan",
    "Klara",
    "Luka",
    "Maja",
    "Nino",
    "Olga",
    "Peter",
    "Rosa",
    "Simon",
    "Tara",
    "Viktor",
]
LAST_NAMES = [
    "Adler",
    "Bauer",
    "Craft",
    "Dolan",
    "Ebner",
    "Fischer",
    "Gruber",
    "Haas",
    "Ilic",
    "Jung",
    "Koch",
    "Lang",
    "Maier",
    "Novak",
    "Ott",
    "Pichler",
    "Reiter",
    "Steiner",
    "Toth",
    "Weber",
]


@dataclass(frozen=True)
class CustomerProfile:
    index: int
    name: str
    email: str
    signup_month: int
    plan_id: str
    interval: str
    failing_card: bool
    event: str | None
    event_month: int | None


def generate_customers(count: int, seed: int = 42) -> list[CustomerProfile]:
    """Same count + seed always returns the exact same list."""
    rng = Random(seed)
    profiles = []
    for i in range(count):
        first = rng.choice(FIRST_NAMES)
        last = rng.choice(LAST_NAMES)
        signup = rng.randrange(MONTHS)
        plan = rng.choices(list(PLAN_WEIGHTS), weights=list(PLAN_WEIGHTS.values()))[0]
        interval = "year" if rng.random() < YEARLY_SHARE else "month"
        failing = rng.random() < FAILING_CARD_SHARE

        # At most one lifecycle event, only if there is a month left for it.
        event = event_month = None
        if signup < MONTHS - 1:
            roll = rng.random()
            if roll < CANCEL_SHARE:
                event = "cancel"
            elif roll < CANCEL_SHARE + UPGRADE_SHARE and plan in UPGRADE_PATH:
                event = "upgrade"
            elif roll < CANCEL_SHARE + UPGRADE_SHARE + DOWNGRADE_SHARE and plan in DOWNGRADE_PATH:
                event = "downgrade"
            if event:
                event_month = rng.randrange(signup + 1, MONTHS)

        profiles.append(
            CustomerProfile(
                index=i,
                name=f"{first} {last}",
                email=f"{first.lower()}.{last.lower()}.{i}@example.com",
                signup_month=signup,
                plan_id=plan,
                interval=interval,
                failing_card=failing,
                event=event,
                event_month=event_month,
            )
        )
    return profiles
