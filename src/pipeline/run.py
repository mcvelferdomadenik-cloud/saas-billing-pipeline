"""CLI entry point: python -m pipeline.run <command>"""

import argparse

from pipeline import seed


def main() -> None:
    parser = argparse.ArgumentParser(prog="pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    p_seed = sub.add_parser("seed", help="Create the fake SaaS business in the Stripe sandbox")
    p_seed.add_argument("--customers", type=int, default=200, help="how many customers to create")
    p_seed.add_argument(
        "--seed", type=int, default=42, help="random seed (same seed = same business)"
    )

    args = parser.parse_args()
    if args.command == "seed":
        seed.run(count=args.customers, seed=args.seed)


if __name__ == "__main__":
    main()
