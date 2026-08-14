#!/usr/bin/env python3
from __future__ import annotations

import argparse

import _path  # noqa: F401
from api_directory.paths import MIN_API_COUNT
from api_directory.validate import main as validate_main


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the normalized catalog")
    parser.add_argument("--min-count", type=int, default=MIN_API_COUNT)
    args = parser.parse_args()
    return validate_main(min_count=args.min_count)


if __name__ == "__main__":
    raise SystemExit(main())
