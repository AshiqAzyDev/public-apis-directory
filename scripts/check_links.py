#!/usr/bin/env python3
from __future__ import annotations

import argparse

import _path  # noqa: F401
from api_directory.check_links import main as check_main


def main() -> int:
    parser = argparse.ArgumentParser(description="Check documentation URL reachability")
    parser.add_argument("--limit", type=int, default=None, help="Check only the first N APIs")
    args = parser.parse_args()
    return check_main(limit=args.limit)


if __name__ == "__main__":
    raise SystemExit(main())
