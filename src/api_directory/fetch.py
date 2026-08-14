"""Fetch the latest public-apis README and commit metadata."""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from api_directory.io_utils import write_json
from api_directory.paths import (
    UPSTREAM_COMMIT_URL,
    UPSTREAM_JSON,
    UPSTREAM_README_URL,
    USER_AGENT,
)


def utc_today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def fetch_upstream(timeout: float = 60.0) -> dict:
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    with httpx.Client(headers=headers, timeout=timeout, follow_redirects=True) as client:
        readme = client.get(UPSTREAM_README_URL)
        readme.raise_for_status()
        commit = client.get(UPSTREAM_COMMIT_URL)
        commit.raise_for_status()
        payload = commit.json()

    record = {
        "fetched_at": utc_now_iso(),
        "fetched_date": utc_today(),
        "branch": "master",
        "commit_sha": payload["sha"],
        "commit_url": payload.get("html_url"),
        "commit_date": payload.get("commit", {}).get("committer", {}).get("date"),
        "source_url": UPSTREAM_README_URL,
        "markdown": readme.text,
    }
    write_json(UPSTREAM_JSON, record)
    return record


def main() -> int:
    record = fetch_upstream()
    print(f"Fetched upstream README ({record['commit_sha'][:12]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
