"""Project configuration.

Loads settings from the .env file in the project root so that secrets
(like the Stripe API key) never appear in code or in git.
"""

import os

from dotenv import load_dotenv

load_dotenv()


def get_stripe_api_key() -> str:
    """Return the Stripe secret key, failing loudly if missing or unsafe."""
    key = os.environ.get("STRIPE_API_KEY")
    if not key:
        raise RuntimeError(
            "STRIPE_API_KEY is not set. Add it to the .env file in the project root."
        )
    if not key.startswith("sk_test_"):
        raise RuntimeError(
            "STRIPE_API_KEY does not look like a sandbox test key (sk_test_...). "
            "Refusing to run against anything but a test environment."
        )
    return key
