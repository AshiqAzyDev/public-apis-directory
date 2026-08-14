"""Normalize parsed rows into the provenance-aware API schema."""

from __future__ import annotations

from typing import Any

from api_directory.fields import (
    canonical_url,
    make_id,
    provider_domain,
    slugify,
    unknown_field,
    upstream_field,
)
from api_directory.io_utils import read_json, write_json
from api_directory.paths import APIS_JSON, PARSED_JSON


def normalize_entry(raw: dict[str, Any]) -> dict[str, Any]:
    original_url = raw["documentation_url"]
    canonical = canonical_url(original_url)
    name = raw["name"]
    category = raw["category"]
    identifier = make_id(name, canonical)

    return {
        "id": identifier,
        "name": name,
        "slug": identifier,
        "description": raw["description"],
        "category": category,
        "tags": [slugify(category)],
        "secondary_categories": [],
        "source": "public-apis",
        "documentation_url": upstream_field(canonical),
        "documentation_url_original": original_url,
        "canonical_url": canonical,
        "provider_domain": provider_domain(canonical),
        "website_url": unknown_field(None),
        "auth": upstream_field(raw["auth"]),
        "https": upstream_field(raw["https"]),
        "cors": upstream_field(raw["cors"] or "Unknown"),
        "auth_location": unknown_field("unknown"),
        "browser_ready": unknown_field("Unknown"),
        "server_side_recommended": unknown_field("Unknown"),
        "free_access": unknown_field("Unknown"),
        "pricing_model": unknown_field("Unknown"),
        "api_type": unknown_field("Unknown"),
        "data_formats": unknown_field([]),
        "sdk_languages": unknown_field([]),
        "openapi_available": unknown_field(None),
        "openapi_url": unknown_field(None),
        "postman_available": unknown_field(None),
        "postman_url": unknown_field(None),
        "rate_limit": unknown_field("Unknown"),
        "commercial_use": unknown_field("Unknown"),
        "registration_required": unknown_field("Unknown"),
        "verification_status": "Upstream Only",
        "confidence": "Low",
        "lifecycle_status": "Unknown",
        "last_verified": None,
        "verification_source": "public-apis",
        "needs_review": False,
        "notes": "",
        "developer_score": {
            "value": None,
            "max": 11,
            "breakdown": {},
            "source_type": "derived",
            "label": "Developer Score (upstream-known fields)",
        },
        "health_score": {
            "value": None,
            "max": 4,
            "breakdown": {},
            "source_type": "unknown",
            "label": "API Health",
        },
        "upstream_line": raw.get("line_number"),
    }


def _merge_category(existing: dict[str, Any], extra_category: str) -> None:
    if extra_category == existing["category"]:
        return
    secondary = existing.setdefault("secondary_categories", [])
    if extra_category not in secondary:
        secondary.append(extra_category)
    tag = slugify(extra_category)
    if tag not in existing["tags"]:
        existing["tags"].append(tag)


def normalize_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One record per canonical documentation URL.

    If upstream lists the same docs URL in multiple categories, the first
    category is primary and the others become secondary tags. The API is still
    shown on every category page where upstream listed it.
    """

    by_url: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for raw in entries:
        api = normalize_entry(raw)
        url = api["canonical_url"]
        if url not in by_url:
            api["secondary_categories"] = []
            by_url[url] = api
            order.append(url)
            continue
        _merge_category(by_url[url], api["category"])

    apis = [by_url[url] for url in order]
    apis.sort(key=lambda item: (item["category"].lower(), item["name"].lower(), item["canonical_url"]))
    return apis


def normalize_parsed() -> list[dict[str, Any]]:
    parsed = read_json(PARSED_JSON)
    if not parsed:
        raise FileNotFoundError(f"Missing parsed catalog at {PARSED_JSON}")
    apis = normalize_entries(parsed["entries"])
    write_json(APIS_JSON, {"apis": apis, "count": len(apis)})
    return apis


def main() -> int:
    apis = normalize_parsed()
    print(f"Normalized {len(apis)} APIs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
