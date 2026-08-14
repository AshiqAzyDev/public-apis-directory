"""Derive fields from upstream data. Never invent provider metadata."""

from __future__ import annotations

from typing import Any

from api_directory.fields import SOURCE_DERIVED, derived_field, value_of
from api_directory.io_utils import read_json, read_yaml, write_json
from api_directory.paths import (
    APIS_JSON,
    LINK_HEALTH_JSON,
    OVERRIDES_JSON,
    SCORING_YML,
)


def derive_browser_ready(https: str, cors: str) -> str:
    if https == "Yes" and cors == "Yes":
        return "Yes"
    if https == "No" or cors == "No":
        return "No"
    return "Unknown"


def derive_server_side_recommended(cors: str) -> str:
    if cors == "No":
        return "Yes"
    return "Unknown"


def derive_registration(auth: str) -> str:
    if auth in {"apiKey", "X-Mashape-Key"}:
        return "API key required"
    if auth == "OAuth":
        return "OAuth authorization required"
    return "Unknown"


def compute_developer_score(api: dict[str, Any], scoring: dict[str, Any]) -> dict[str, Any]:
    points = scoring.get("points", {})
    breakdown: dict[str, int] = {}
    total = 0

    def add(key: str, enabled: bool) -> None:
        nonlocal total
        value = int(points.get(key, 0)) if enabled else 0
        breakdown[key] = value
        total += value

    add("https_yes", value_of(api["https"]) == "Yes")
    add("cors_yes", value_of(api["cors"]) == "Yes")
    add("auth_no", value_of(api["auth"]) == "No")
    add("openapi", value_of(api.get("openapi_available")) in {True, "Yes"})
    add("postman", value_of(api.get("postman_available")) in {True, "Yes"})
    sdk = value_of(api.get("sdk_languages"), [])
    add("official_sdk", bool(sdk))
    add("free_access_verified", value_of(api.get("free_access")) in {"Free", "Free Tier", "Open"})

    return {
        "value": total,
        "max": int(scoring.get("max", 11)),
        "breakdown": breakdown,
        "source_type": SOURCE_DERIVED,
        "label": scoring.get("label", "Developer Score (upstream-known fields)"),
    }


def classify_link_status(code: Any) -> str:
    if code is None:
        return "Unknown"
    if isinstance(code, str):
        lowered = code.lower()
        if lowered in {"timeout", "dns", "dns error"}:
            return code
        if lowered.isdigit():
            code = int(lowered)
        else:
            return "Unknown"
    if 200 <= int(code) < 300:
        return "200 OK"
    if 300 <= int(code) < 400:
        return "3xx Redirect"
    if 400 <= int(code) < 500:
        return "4xx Broken"
    if 500 <= int(code) < 600:
        return "5xx Server Error"
    return "Unknown"


def compute_health_score(api: dict[str, Any], health: dict[str, Any] | None) -> dict[str, Any]:
    if not health:
        return {
            "value": None,
            "max": 4,
            "breakdown": {},
            "source_type": "unknown",
            "label": "API Health",
        }

    result = health.get("results", {}).get(api["id"]) or health.get("results", {}).get(
        api["canonical_url"]
    )
    if not result:
        return {
            "value": None,
            "max": 4,
            "breakdown": {},
            "source_type": "unknown",
            "label": "API Health",
        }

    status = result.get("classification") or classify_link_status(result.get("status_code"))
    reachable = status in {"200 OK", "3xx Redirect"}
    https_url = api["canonical_url"].startswith("https://")
    docs_available = reachable
    not_dead = api.get("lifecycle_status") != "Dead"
    breakdown = {
        "url_reachable": int(reachable),
        "https_url": int(https_url),
        "documentation_available": int(docs_available),
        "not_dead": int(not_dead),
    }
    return {
        "value": sum(breakdown.values()),
        "max": 4,
        "breakdown": breakdown,
        "source_type": "derived",
        "label": "API Health",
        "link_classification": status,
    }


def apply_lifecycle(api: dict[str, Any], health: dict[str, Any] | None) -> None:
    if not health:
        api["lifecycle_status"] = "Unknown"
        return
    result = health.get("results", {}).get(api["id"]) or health.get("results", {}).get(
        api["canonical_url"]
    )
    if not result:
        api["lifecycle_status"] = "Unknown"
        return

    streak = int(result.get("consecutive_failures", 0))
    status = result.get("classification") or classify_link_status(result.get("status_code"))
    api["last_verified"] = result.get("checked_at")
    if result.get("checked_at"):
        api["verification_source"] = "public-apis + link-check"

    if streak >= 3 and status not in {"200 OK", "3xx Redirect"}:
        api["lifecycle_status"] = "Dead"
        api["verification_status"] = "Dead"
        return
    if status == "200 OK":
        api["lifecycle_status"] = "Active"
        if api.get("verification_status") == "Upstream Only":
            api["verification_status"] = "Partially Verified"
            api["confidence"] = "Medium"
        return
    if status == "3xx Redirect":
        api["lifecycle_status"] = "Possibly Active"
        return
    if status in {"4xx Broken", "5xx Server Error", "Timeout", "DNS Error"}:
        api["lifecycle_status"] = "Needs Verification"
        return
    api["lifecycle_status"] = "Unknown"


def apply_overrides(apis: list[dict[str, Any]], overrides: list[dict[str, Any]]) -> None:
    by_id = {api["id"]: api for api in apis}
    protected = {"auth", "https", "cors", "name", "description", "category", "documentation_url"}
    for override in overrides:
        target = by_id.get(override.get("id"))
        if not target:
            continue
        for key, payload in override.items():
            if key in {"id", "name"}:
                continue
            if key in protected:
                continue
            if isinstance(payload, dict) and "value" in payload:
                target[key] = payload
                if payload.get("source_type") == "provider_documentation":
                    if target.get("verification_status") in {"Upstream Only", "Needs Review"}:
                        target["verification_status"] = "Partially Verified"
                        target["confidence"] = "Medium"


def enrich_apis(apis: list[dict[str, Any]]) -> list[dict[str, Any]]:
    scoring = read_yaml(SCORING_YML)
    health = read_json(LINK_HEALTH_JSON, default={"results": {}})
    overrides = read_json(OVERRIDES_JSON, default=[]) or []

    for api in apis:
        https = value_of(api["https"], "Unknown")
        cors = value_of(api["cors"], "Unknown")
        auth = value_of(api["auth"], "Unknown")
        api["browser_ready"] = derived_field(derive_browser_ready(https, cors))
        api["server_side_recommended"] = derived_field(derive_server_side_recommended(cors))
        api["registration_required"] = derived_field(derive_registration(auth))
        api["auth_location"] = derived_field("unknown")
        apply_lifecycle(api, health)
        api["developer_score"] = compute_developer_score(api, scoring)
        api["health_score"] = compute_health_score(api, health)

    apply_overrides(apis, overrides)
    return apis


def enrich_normalized() -> list[dict[str, Any]]:
    payload = read_json(APIS_JSON)
    if not payload:
        raise FileNotFoundError(f"Missing normalized catalog at {APIS_JSON}")
    apis = enrich_apis(payload["apis"])
    write_json(APIS_JSON, {"apis": apis, "count": len(apis)})
    return apis


def main() -> int:
    apis = enrich_normalized()
    print(f"Enriched {len(apis)} APIs (derived fields only)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
