"""CLI entry point: python -m pipeline.run <command>"""

import argparse

from pipeline import seed


def main() -> None:
    parser = argparse.ArgumentParser(prog="pipeline")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("seed", help="Create the fake SaaS business in the Stripe sandbox")
    args = parser.parse_args()

    if args.command == "seed":
        seed.run()


if __name__ == "__main__":
    main()