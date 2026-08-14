"""HTTP reachability checks. Never delete APIs after a failed check."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

import httpx

from api_directory.enrich import classify_link_status
from api_directory.fields import value_of
from api_directory.io_utils import read_json, write_json
from api_directory.paths import (
    APIS_JSON,
    DEAD_FAILURE_STREAK,
    LINK_HEALTH_JSON,
    USER_AGENT,
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def classify_exception(exc: Exception) -> str:
    if isinstance(exc, httpx.TimeoutException):
        return "Timeout"
    if isinstance(exc, httpx.ConnectError):
        message = str(exc).lower()
        if "name or service not known" in message or "getaddrinfo" in message or "dns" in message:
            return "DNS Error"
        return "DNS Error"
    return "Unknown"


def check_url(
    client: httpx.Client,
    url: str,
    retries: int = 3,
    timeout: float = 12.0,
) -> dict[str, Any]:
    last_error = "Unknown"
    for attempt in range(retries):
        try:
            response = client.head(url, timeout=timeout)
            if response.status_code in {405, 501} or response.status_code >= 400:
                response = client.get(url, timeout=timeout)
            classification = classify_link_status(response.status_code)
            if response.status_code < 500:
                return {
                    "url": url,
                    "status_code": response.status_code,
                    "classification": classification,
                    "final_url": str(response.url),
                    "attempts": attempt + 1,
                    "ok": response.status_code < 400,
                }
            last_error = classification
        except Exception as exc:  # noqa: BLE001 — classify, don't crash the catalog
            last_error = classify_exception(exc)
        time.sleep(0.5 * (attempt + 1))

    return {
        "url": url,
        "status_code": None,
        "classification": last_error,
        "final_url": None,
        "attempts": retries,
        "ok": False,
    }


def merge_history(previous: dict[str, Any] | None, current: dict[str, Any]) -> dict[str, Any]:
    previous = previous or {}
    history = list(previous.get("history") or [])
    history.append(
        {
            "checked_at": current["checked_at"],
            "classification": current["classification"],
            "status_code": current.get("status_code"),
        }
    )
    history = history[-10:]
    failed = current["classification"] not in {"200 OK", "3xx Redirect"}
    streak = int(previous.get("consecutive_failures") or 0)
    streak = streak + 1 if failed else 0
    current["history"] = history
    current["consecutive_failures"] = streak
    current["dead_candidate"] = streak >= DEAD_FAILURE_STREAK
    return current


def check_links(
    limit: int | None = None,
    delay: float = 0.05,
) -> dict[str, Any]:
    payload = read_json(APIS_JSON)
    if not payload:
        raise FileNotFoundError(f"Missing normalized catalog at {APIS_JSON}")
    previous = read_json(LINK_HEALTH_JSON, default={"results": {}}) or {"results": {}}
    previous_results = previous.get("results") or {}

    apis = payload["apis"]
    if limit is not None:
        apis = apis[:limit]

    results: dict[str, Any] = dict(previous_results)
    headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    checked_at = utc_now_iso()

    with httpx.Client(headers=headers, follow_redirects=True) as client:
        for api in apis:
            url = value_of(api["documentation_url"], api["canonical_url"])
            outcome = check_url(client, url)
            outcome["checked_at"] = checked_at
            outcome["id"] = api["id"]
            results[api["id"]] = merge_history(previous_results.get(api["id"]), outcome)
            if delay:
                time.sleep(delay)

    record = {
        "checked_at": checked_at,
        "checked_count": len(apis),
        "results": results,
    }
    write_json(LINK_HEALTH_JSON, record)
    return record


def main(limit: int | None = None) -> int:
    record = check_links(limit=limit)
    print(f"Checked {record['checked_count']} documentation URLs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
