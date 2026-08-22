#!/usr/bin/env python
"""Create the four Dodo products a self-serve plan needs, and print their ids.

    python scripts/dodo_products.py --starter-monthly 99900 --starter-annual 999000 \
                                    --growth-monthly 499900 --growth-annual 4999000

Prices are **required and in minor units** - paise for INR, so `99900` is ₹999.
Neither has a default. A default price would be a number nobody decided showing up
on a real checkout, and `lib/pricing.ts` already carries the scar from that: the
public pricing page was deleted rather than ship a figure that had not been agreed.

**Idempotent.** Products are matched by name, so re-running reports the existing id
instead of creating a fifth Starter. That matters because Dodo has no unique
constraint on product names - nothing but this check stops a re-run from quietly
doubling your catalogue.

Creates in whatever `DODO_ENVIRONMENT` says, which defaults to `test_mode`. Pass
`--live` to mean it.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Windows consoles default to cp1252, which cannot encode the rupee sign this
# script prints in its own help text - and argparse writes help *before* any of
# our code runs, so `--help` died with a UnicodeEncodeError rather than showing
# help. Reconfiguring the stream is the fix that also covers the amounts printed
# further down; dropping the symbol would only have moved the problem.
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parents[1]

# Name -> (plan, period, env var to paste the id into). The name is also the
# idempotency key, so changing one here orphans the product it used to match.
PRODUCTS = {
    "CallFlow Starter (monthly)": ("starter", "monthly", "DODO_PRODUCT_STARTER_MONTHLY"),
    "CallFlow Starter (annual)": ("starter", "annual", "DODO_PRODUCT_STARTER_ANNUAL"),
    "CallFlow Growth (monthly)": ("growth", "monthly", "DODO_PRODUCT_GROWTH_MONTHLY"),
    "CallFlow Growth (annual)": ("growth", "annual", "DODO_PRODUCT_GROWTH_ANNUAL"),
}


def recurring_price(amount_minor: int, period: str, currency: str) -> dict[str, object]:
    """A Dodo `recurring_price`.

    Monthly bills every month for a one-month term; annual bills once for a
    twelve-month term. `payment_frequency_*` is how often money moves and
    `subscription_period_*` is how long the commitment runs - setting annual to
    bill monthly over a year is a different product, and an easy accident.
    """
    interval = "Month" if period == "monthly" else "Year"
    return {
        "type": "recurring_price",
        "price": amount_minor,
        "currency": currency,
        "discount": 0,
        "purchasing_power_parity": False,
        "payment_frequency_count": 1,
        "payment_frequency_interval": interval,
        "subscription_period_count": 1,
        "subscription_period_interval": interval,
        "trial_period_days": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ("starter-monthly", "starter-annual", "growth-monthly", "growth-annual"):
        parser.add_argument(
            f"--{flag}",
            type=int,
            required=True,
            help=f"{flag} price in minor units (paise for INR)",
        )
    parser.add_argument("--currency", default="INR")
    parser.add_argument(
        "--live",
        action="store_true",
        help="create in live_mode. Without this the script uses test_mode whatever "
        "DODO_ENVIRONMENT says, so a stray run cannot make real products.",
    )
    args = parser.parse_args()

    try:
        from dotenv import load_dotenv
    except ImportError:
        print("Install the API's dependencies first: pip install -e 'apps/api[dev]'")
        return 1
    load_dotenv(REPO_ROOT / ".env")

    api_key = os.getenv("DODO_API_KEY", "").strip()
    if not api_key:
        print(
            "DODO_API_KEY is not set in .env.\n\n"
            "Get one from the Dodo dashboard (Developer -> API Keys) and put it in the\n"
            "repo-root .env, then re-run. Nothing is created without it."
        )
        return 1

    try:
        from dodopayments import DodoPayments
    except ImportError:
        print("The SDK is missing: pip install dodopayments")
        return 1

    # Test unless explicitly told otherwise. Reading DODO_ENVIRONMENT here would let
    # a .env left on live_mode create real products from a routine re-run.
    environment = "live_mode" if args.live else "test_mode"
    client = DodoPayments(bearer_token=api_key, environment=environment)

    prices = {
        ("starter", "monthly"): args.starter_monthly,
        ("starter", "annual"): args.starter_annual,
        ("growth", "monthly"): args.growth_monthly,
        ("growth", "annual"): args.growth_annual,
    }

    print(f"Environment: {environment}\n")

    existing: dict[str, str] = {}
    try:
        for product in client.products.list():
            name = getattr(product, "name", None)
            if name in PRODUCTS:
                existing[name] = product.product_id
    except Exception as exc:  # noqa: BLE001 - one message beats a traceback here
        print(f"Could not list existing products, so a re-run might duplicate: {exc}")
        return 1

    resolved: dict[str, str] = {}
    for name, (plan, period, env_var) in PRODUCTS.items():
        if name in existing:
            resolved[env_var] = existing[name]
            print(f"  exists   {name:32} {existing[name]}")
            continue
        try:
            created = client.products.create(
                name=name,
                tax_category="saas",
                price=recurring_price(prices[(plan, period)], period, args.currency),
                description=f"CallFlow AI {plan.capitalize()} plan, billed {period}.",
                metadata={"plan_id": plan, "period": period},
            )
        except Exception as exc:  # noqa: BLE001
            print(f"  FAILED   {name:32} {exc}")
            return 1
        resolved[env_var] = created.product_id
        amount = prices[(plan, period)] / 100
        print(f"  created  {name:32} {created.product_id}   {args.currency} {amount:,.2f}")

    print("\nPaste these into .env, then restart the API:\n")
    for env_var in (
        "DODO_PRODUCT_STARTER_MONTHLY",
        "DODO_PRODUCT_STARTER_ANNUAL",
        "DODO_PRODUCT_GROWTH_MONTHLY",
        "DODO_PRODUCT_GROWTH_ANNUAL",
    ):
        print(f"{env_var}={resolved.get(env_var, '')}")

    print(
        "\nStill to do by hand: the webhook endpoint (Developer -> Webhooks), pointed at\n"
        "<your public URL>/api/v1/webhooks/dodo, and its signing secret into\n"
        "DODO_WEBHOOK_KEY. There is no API for that, and without it a paid checkout\n"
        "never becomes an active subscription."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
