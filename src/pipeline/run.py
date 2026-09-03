"""CLI entry point: python -m pipeline.run <command>"""

import argparse
import logging

from pipeline import extract, seed


def main() -> None:
    parser = argparse.ArgumentParser(prog="pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    p_seed = sub.add_parser("seed", help="Create the fake SaaS business in the Stripe sandbox")
    p_seed.add_argument("--customers", type=int, default=200, help="how many customers to create")
    p_seed.add_argument(
        "--seed", type=int, default=42, help="random seed (same seed = same business)"
    )

    p_sync = sub.add_parser("sync", help="Extract raw Stripe data into data/raw/")
    p_sync.add_argument(
        "--full", action="store_true", help="force a full backfill instead of incremental"
    )

    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    if args.command == "seed":
        seed.run(count=args.customers, seed=args.seed)
    elif args.command == "sync":
        extract.sync(full=args.full)


if __name__ == "__main__":
    main()
