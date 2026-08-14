"""Run the full catalog pipeline."""

from __future__ import annotations

import argparse
import copy

from api_directory.changelog import previous_apis, write_changelog
from api_directory.deduplicate import deduplicate_normalized
from api_directory.enrich import enrich_normalized
from api_directory.fetch import fetch_upstream
from api_directory.generate import generate_docs
from api_directory.normalize import normalize_parsed
from api_directory.parse import parse_upstream
from api_directory.paths import MIN_API_COUNT
from api_directory.validate import ValidationError, validate_apis


def build(skip_fetch: bool = False, min_count: int = MIN_API_COUNT) -> int:
    previous = copy.deepcopy(previous_apis())
    if not skip_fetch:
        upstream = fetch_upstream()
        commit = upstream.get("commit_sha")
        print(f"Fetched upstream {commit}")
    else:
        commit = None
        print("Skipping fetch; using existing upstream.json")

    parsed = parse_upstream()
    print(f"Parsed {parsed['count']} entries")
    apis = normalize_parsed()
    print(f"Normalized {len(apis)}")
    flags = deduplicate_normalized()
    print(f"Flagged {len(flags)} possible duplicate pairs")
    apis = enrich_normalized()
    print(f"Enriched {len(apis)}")

    errors = validate_apis(apis, min_count=min_count)
    if errors:
        print("Validation failed:")
        for error in errors[:50]:
            print(f" - {error}")
        return 1

    write_changelog(previous, apis, commit)
    stats = generate_docs()
    print(f"Build complete: {stats['total_apis']} APIs, {stats['total_categories']} categories")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the public APIs directory")
    parser.add_argument("--skip-fetch", action="store_true", help="Reuse data/raw/upstream.json")
    parser.add_argument("--min-count", type=int, default=MIN_API_COUNT)
    args = parser.parse_args()
    return build(skip_fetch=args.skip_fetch, min_count=args.min_count)


if __name__ == "__main__":
    raise SystemExit(main())
