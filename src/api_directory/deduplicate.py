"""Flag possible duplicates. Never merge or delete ambiguous entries."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from rapidfuzz import fuzz

from api_directory.fields import normalize_provider_name
from api_directory.io_utils import read_json, write_json
from api_directory.paths import APIS_JSON, DUPLICATES_JSON, FUZZY_NAME_THRESHOLD


def detect_duplicates(apis: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flags: list[dict[str, Any]] = []
    seen_pairs: set[tuple[str, str]] = set()

    def add_flag(left: dict[str, Any], right: dict[str, Any], reason: str, detail: str) -> None:
        pair = tuple(sorted((left["id"], right["id"])))
        if pair in seen_pairs:
            return
        seen_pairs.add(pair)
        flags.append(
            {
                "left_id": left["id"],
                "right_id": right["id"],
                "left_name": left["name"],
                "right_name": right["name"],
                "left_url": left["canonical_url"],
                "right_url": right["canonical_url"],
                "reason": reason,
                "detail": detail,
            }
        )
        left["needs_review"] = True
        right["needs_review"] = True
        if left["verification_status"] == "Upstream Only":
            left["verification_status"] = "Needs Review"
        if right["verification_status"] == "Upstream Only":
            right["verification_status"] = "Needs Review"

    by_name_domain: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    by_domain: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_provider: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for api in apis:
        name_key = api["name"].strip().lower()
        by_name_domain[(name_key, api["provider_domain"])].append(api)
        by_domain[api["provider_domain"]].append(api)
        provider = normalize_provider_name(api["name"])
        if provider:
            by_provider[provider].append(api)

    for group in by_name_domain.values():
        if len(group) < 2:
            continue
        for index, left in enumerate(group):
            for right in group[index + 1 :]:
                add_flag(
                    left,
                    right,
                    "same_name_and_domain",
                    "Same display name and registrable domain",
                )

    for domain, group in by_domain.items():
        if not domain or len(group) < 2:
            continue
        for index, left in enumerate(group):
            for right in group[index + 1 :]:
                if left["name"].strip().lower() == right["name"].strip().lower():
                    continue
                score = fuzz.ratio(left["name"].lower(), right["name"].lower())
                if score >= FUZZY_NAME_THRESHOLD:
                    add_flag(
                        left,
                        right,
                        "fuzzy_name_same_domain",
                        f"Name similarity {score} on {domain}",
                    )

    for provider, group in by_provider.items():
        if len(group) < 2:
            continue
        for index, left in enumerate(group):
            for right in group[index + 1 :]:
                add_flag(
                    left,
                    right,
                    "normalized_provider_name",
                    f"Normalized provider name '{provider}'",
                )

    flags.sort(key=lambda item: (item["reason"], item["left_name"], item["right_name"]))
    return flags


def duplicate_canonical_urls(apis: list[dict[str, Any]]) -> list[str]:
    counts: dict[str, int] = defaultdict(int)
    for api in apis:
        counts[api["canonical_url"]] += 1
    return sorted(url for url, count in counts.items() if count > 1)


def deduplicate_normalized() -> list[dict[str, Any]]:
    payload = read_json(APIS_JSON)
    if not payload:
        raise FileNotFoundError(f"Missing normalized catalog at {APIS_JSON}")
    apis = payload["apis"]
    flags = detect_duplicates(apis)
    write_json(
        DUPLICATES_JSON,
        {
            "count": len(flags),
            "policy": "Flag only. Do not merge or delete ambiguous entries.",
            "items": flags,
        },
    )
    write_json(APIS_JSON, {"apis": apis, "count": len(apis)})
    return flags


def main() -> int:
    flags = deduplicate_normalized()
    print(f"Flagged {len(flags)} possible duplicate pairs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
