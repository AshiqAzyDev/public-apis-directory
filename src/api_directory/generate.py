"""Generate GitHub-native documentation from the normalized catalog."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

from api_directory.fields import category_slug, value_of
from api_directory.io_utils import read_json, read_yaml, write_json, write_text
from api_directory.markdown import banner, field_text, link, score_text, table
from api_directory.paths import (
    APIS_JSON,
    CATEGORIES_DIR,
    CATEGORIES_JSON,
    CATEGORIES_YML,
    DUPLICATES_JSON,
    GENERATED_APIS,
    GENERATED_README,
    INDEXES_DIR,
    LINK_HEALTH_JSON,
    ROOT_README,
    STATS_JSON,
    UPSTREAM_JSON,
    USE_CASES_YML,
)


def utc_today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def load_apis() -> list[dict[str, Any]]:
    payload = read_json(APIS_JSON)
    if not payload:
        raise FileNotFoundError(f"Missing normalized catalog at {APIS_JSON}")
    return payload["apis"]


def catalog_date() -> str:
    upstream = read_json(UPSTREAM_JSON, default={}) or {}
    return upstream.get("fetched_date") or utc_today()


def compute_stats(apis: list[dict[str, Any]], extras: dict[str, Any] | None = None) -> dict[str, Any]:
    def count_equals(key: str, expected: str) -> int:
        return sum(1 for api in apis if value_of(api.get(key)) == expected)

    health = read_json(LINK_HEALTH_JSON, default={}) or {}
    results = health.get("results") or {}
    broken = 0
    for result in results.values():
        classification = result.get("classification")
        if classification in {"4xx Broken", "5xx Server Error", "Timeout", "DNS Error"}:
            broken += 1

    duplicates = read_json(DUPLICATES_JSON, default={"items": []}) or {"items": []}
    categories = sorted({api["category"] for api in apis})
    stats = {
        "total_apis": len(apis),
        "total_categories": len(categories),
        "no_auth": count_equals("auth", "No"),
        "api_key": count_equals("auth", "apiKey"),
        "oauth": count_equals("auth", "OAuth"),
        "mashape": count_equals("auth", "X-Mashape-Key"),
        "user_agent": count_equals("auth", "User-Agent"),
        "https_yes": count_equals("https", "Yes"),
        "https_no": count_equals("https", "No"),
        "cors_yes": count_equals("cors", "Yes"),
        "cors_no": count_equals("cors", "No"),
        "cors_unknown": count_equals("cors", "Unknown"),
        "browser_ready": count_equals("browser_ready", "Yes"),
        "free": count_equals("free_access", "Free"),
        "free_tier": count_equals("free_access", "Free Tier"),
        "rest": count_equals("api_type", "REST"),
        "graphql": count_equals("api_type", "GraphQL"),
        "openapi": sum(1 for api in apis if value_of(api.get("openapi_available")) in {True, "Yes"}),
        "postman": sum(1 for api in apis if value_of(api.get("postman_available")) in {True, "Yes"}),
        "verified": sum(1 for api in apis if api.get("verification_status") == "Verified"),
        "partially_verified": sum(
            1 for api in apis if api.get("verification_status") == "Partially Verified"
        ),
        "upstream_only": sum(1 for api in apis if api.get("verification_status") == "Upstream Only"),
        "needs_review": sum(1 for api in apis if api.get("needs_review")),
        "unknown_metadata": len(apis),
        "broken_links": broken,
        "duplicate_pairs": len(duplicates.get("items") or []),
        "dead": sum(1 for api in apis if api.get("lifecycle_status") == "Dead"),
        "generated": catalog_date(),
    }
    if extras:
        stats.update(extras)
    return stats


def api_categories(api: dict[str, Any]) -> list[str]:
    names = [api["category"]]
    for extra in api.get("secondary_categories") or []:
        if extra not in names:
            names.append(extra)
    return names


def category_breakdown(apis: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for api in apis:
        for name in api_categories(api):
            grouped[name].append(api)
    config = read_yaml(CATEGORIES_YML) or {}
    rows = []
    for name in sorted(grouped, key=str.lower):
        items = grouped[name]
        info = config.get(name) or {}
        rows.append(
            {
                "name": name,
                "slug": category_slug(name),
                "count": len(items),
                "description": info.get("description") or f"Public APIs in the {name} category.",
                "related": info.get("related") or [],
                "no_auth": sum(1 for api in items if value_of(api["auth"]) == "No"),
                "https_yes": sum(1 for api in items if value_of(api["https"]) == "Yes"),
                "cors_yes": sum(1 for api in items if value_of(api["cors"]) == "Yes"),
                "browser_ready": sum(1 for api in items if value_of(api["browser_ready"]) == "Yes"),
            }
        )
    return rows


def freshness(stats: dict[str, Any]) -> str:
    upstream = read_json(UPSTREAM_JSON, default={}) or {}
    health = read_json(LINK_HEALTH_JSON, default={}) or {}
    build_id = upstream.get("commit_sha") or stats.get("catalog_build") or "unknown"
    short_build = build_id[:7] if build_id != "unknown" else "unknown"
    return table(
        ["Field", "Value"],
        [
            ["Generated", stats.get("generated") or utc_today()],
            ["Catalog build", f"`{short_build}`"],
            ["Last link check", health.get("checked_at") or "Not run"],
            ["Last enrichment", stats.get("generated") or utc_today()],
        ],
    )


def api_table(apis: list[dict[str, Any]], include_category: bool = False) -> str:
    headers = ["API", "Description", "Auth", "HTTPS", "CORS", "Browser ready", "Score"]
    if include_category:
        headers.insert(2, "Category")
    rows = []
    for api in apis:
        docs = value_of(api["documentation_url"], api["canonical_url"])
        row: list[Any] = [link(api["name"], docs), api["description"]]
        if include_category:
            slug = category_slug(api["category"])
            row.append(link(api["category"], f"../categories/{slug}.md"))
        row.extend(
            [
                f"`{field_text(api, 'auth')}`",
                field_text(api, "https"),
                field_text(api, "cors"),
                field_text(api, "browser_ready"),
                score_text(api),
            ]
        )
        rows.append(row)
    return table(headers, rows)


def top_categories(categories: list[dict[str, Any]], limit: int = 10) -> list[dict[str, Any]]:
    return sorted(categories, key=lambda item: (-item["count"], item["name"].lower()))[:limit]


def render_root_readme(apis: list[dict[str, Any]], stats: dict[str, Any], categories: list[dict[str, Any]]) -> str:
    use_cases = read_yaml(USE_CASES_YML) or {}
    sha = (read_json(UPSTREAM_JSON, default={}) or {}).get("commit_sha", "unknown")
    short_sha = sha[:7] if sha != "unknown" else "unknown"

    badge_apis = f"https://img.shields.io/badge/APIs-{stats['total_apis']}-blue"
    badge_cats = f"https://img.shields.io/badge/categories-{stats['total_categories']}-informational"
    badge_license = "https://img.shields.io/badge/license-MIT-green"
    badge_json = "https://img.shields.io/badge/format-JSON-orange"

    category_rows = [
        [
            link(item["name"], f"generated/categories/{item['slug']}.md"),
            item["count"],
            item["no_auth"],
            item["https_yes"],
            item["cors_yes"],
            item["browser_ready"],
        ]
        for item in categories
    ]

    top_category_rows = [
        [
            link(item["name"], f"generated/categories/{item['slug']}.md"),
            item["count"],
            item["browser_ready"],
        ]
        for item in top_categories(categories)
    ]

    stats_rows = [
        ["Total APIs", stats["total_apis"]],
        ["Total categories", stats["total_categories"]],
        ["No-auth APIs", stats["no_auth"]],
        ["API-key APIs", stats["api_key"]],
        ["OAuth APIs", stats["oauth"]],
        ["HTTPS APIs", stats["https_yes"]],
        ["CORS-enabled APIs", stats["cors_yes"]],
        ["Browser-ready APIs", stats["browser_ready"]],
        ["Free APIs (verified)", stats["free"]],
        ["Free-tier APIs (verified)", stats["free_tier"]],
        ["REST APIs (verified)", stats["rest"]],
        ["GraphQL APIs (verified)", stats["graphql"]],
        ["OpenAPI APIs (verified)", stats["openapi"]],
        ["Postman APIs (verified)", stats["postman"]],
        ["Verified APIs", stats["verified"]],
        ["Pending full verification", stats["upstream_only"]],
        ["Unknown enrichment fields", "Most enrichment fields are Unknown until verified"],
        ["Broken links (last check)", stats["broken_links"]],
        ["Possible duplicate pairs", stats["duplicate_pairs"]],
    ]

    use_case_lines = []
    for key in ("frontend", "backend", "no_auth", "prototyping", "ai", "saas"):
        case = use_cases.get(key) or {}
        title = case.get("title", key)
        criteria = case.get("criteria_text", "")
        description = case.get("description", "")
        index = case.get("index")
        use_case_lines.append(f"### {title}")
        use_case_lines.append("")
        use_case_lines.append(description)
        use_case_lines.append("")
        use_case_lines.append(f"**Criteria:** `{criteria}`")
        if index:
            use_case_lines.append("")
            use_case_lines.append(f"→ [Browse matching APIs](generated/indexes/{index})")
        use_case_lines.append("")

    lines = [
        banner(),
        "",
        "# Public APIs Master Index",
        "",
        "A curated, structured directory of **public APIs** — searchable, filterable, and ready to integrate "
        "from JSON or Markdown.",
        "",
        f"![API count]({badge_apis}) "
        f"![Category count]({badge_cats}) "
        f"![License: MIT]({badge_license}) "
        f"![JSON dataset]({badge_json})",
        "",
        f"**{stats['total_apis']:,} APIs** across **{stats['total_categories']} categories**, "
        "with filter indexes, category pages, health checks, and a normalized JSON export.",
        "",
        "## Table of contents",
        "",
        "- [Start here](#start-here)",
        "- [At a glance](#at-a-glance)",
        "- [What you get](#what-you-get)",
        "- [Browse the catalog](#browse-the-catalog)",
        "- [Quick start (developers)](#quick-start-developers)",
        "- [Data freshness](#data-freshness)",
        "- [API statistics](#api-statistics)",
        "- [Category explorer](#category-explorer)",
        "- [Authentication explorer](#authentication-explorer)",
        "- [Discovery by use case](#discovery-by-use-case)",
        "- [Developer score & health](#developer-score)",
        "- [Contributing & automation](#contributing--automation)",
        "- [Data sources & license](#data-sources)",
        "",
        "## Start here",
        "",
        "| Goal | Where to go |",
        "| --- | --- |",
        f"| Browse by topic | [Category pages](generated/README.md) ({stats['total_categories']} categories) |",
        f"| Call from the browser | [{stats['browser_ready']} browser-ready APIs](generated/indexes/browser-ready.md) (HTTPS + CORS) |",
        f"| Skip authentication setup | [{stats['no_auth']} no-auth APIs](generated/indexes/no-auth.md) |",
        "| Build a hackathon MVP | [Prototyping index](generated/indexes/prototyping.md) (no auth + HTTPS) |",
        "| Search or integrate programmatically | [`data/normalized/apis.json`](data/normalized/apis.json) · [search.json](generated/indexes/search.json) |",
        "| See every API in one file | [generated/APIs.md](generated/APIs.md) |",
        "",
        "## At a glance",
        "",
        table(
            ["Metric", "Count"],
            [
                ["Total APIs", f"{stats['total_apis']:,}"],
                ["Categories", stats["total_categories"]],
                ["No authentication", stats["no_auth"]],
                ["Browser-ready (HTTPS + CORS)", stats["browser_ready"]],
                ["HTTPS", stats["https_yes"]],
                ["CORS enabled", stats["cors_yes"]],
            ],
        ),
        "",
        "## What you get",
        "",
        "A **developer-first API directory** maintained in this repository:",
        "",
        "- **Structured JSON** — one record per API with stable IDs, slugs, and normalized fields.",
        "- **Filter indexes** — curated views for no-auth, browser-ready, prototyping, AI, SaaS, and more.",
        "- **Category pages** — per-topic breakdowns with auth, HTTPS, and CORS counts.",
        "- **Honest metadata** — enrichment fields stay `Unknown` until verified from official docs.",
        "- **Derived labels** — browser-ready and developer scores are computed transparently, not guessed.",
        "- **Health tracking** — documentation links are checked on a schedule; broken links are flagged, not hidden.",
        "",
        "Accuracy is preferred over completeness. Completeness is preferred over decoration.",
        "",
        "## Browse the catalog",
        "",
        "### Popular categories",
        "",
        "Largest categories by API count. See [all categories](#category-explorer) below.",
        "",
        table(["Category", "APIs", "Browser ready"], top_category_rows),
        "",
        "### Filter indexes",
        "",
        "| Filter | APIs |",
        "| --- | ---: |",
        f"| [No authentication](generated/indexes/no-auth.md) | {stats['no_auth']} |",
        f"| [API key](generated/indexes/api-key.md) | {stats['api_key']} |",
        f"| [OAuth](generated/indexes/oauth.md) | {stats['oauth']} |",
        f"| [Browser-ready](generated/indexes/browser-ready.md) | {stats['browser_ready']} |",
        f"| [HTTPS](generated/indexes/https.md) | {stats['https_yes']} |",
        f"| [CORS enabled](generated/indexes/cors.md) | {stats['cors_yes']} |",
        f"| [Prototyping & students](generated/indexes/prototyping.md) | — |",
        f"| [AI & ML](generated/indexes/ai.md) | — |",
        f"| [SaaS development](generated/indexes/saas.md) | — |",
        "",
        "Free-tier, REST, GraphQL, OpenAPI, and Postman indexes list only **verified** entries "
        f"({stats['free']} free, {stats['rest']} REST, {stats['graphql']} GraphQL today).",
        "",
        "## Quick start (developers)",
        "",
        "Clone, install, rebuild the catalog, and run tests:",
        "",
        "```bash",
        "git clone https://github.com/AshiqAzyDev/public-apis-directory.git",
        "cd public-apis-directory",
        "pip install -r requirements.txt",
        "python scripts/build.py",
        "pytest",
        "```",
        "",
        "Pipeline scripts live in [`scripts/`](scripts/) if you need to run individual steps.",
        "",
        "Key paths:",
        "",
        "| Path | Contents |",
        "| --- | --- |",
        "| [`data/normalized/apis.json`](data/normalized/apis.json) | Full normalized catalog |",
        "| [`generated/`](generated/) | Markdown indexes and category pages |",
        "| [`config/`](config/) | Scoring rules, category blurbs, use-case criteria |",
        "| [`src/api_directory/`](src/api_directory/) | Pipeline source code |",
        "",
        "## Data freshness",
        "",
        freshness(stats),
        "",
        f"Catalog build `{short_sha}` is recorded at generation time so every export stays auditable.",
        "",
        "## API statistics",
        "",
        "Full counts from the normalized dataset. Verified enrichment fields remain `Unknown` in v1 "
        "unless recorded in [`data/metadata/overrides.json`](data/metadata/overrides.json).",
        "",
        table(["Metric", "Count"], stats_rows),
        "",
        "## Category explorer",
        "",
        "All categories with per-category counts for authentication, transport, and browser compatibility.",
        "",
        table(
            ["Category", "APIs", "No auth", "HTTPS", "CORS", "Browser ready"],
            category_rows,
        ),
        "",
        "## Authentication explorer",
        "",
        table(
            ["Authentication", "APIs", "Index"],
            [
                ["No", stats["no_auth"], link("Browse", "generated/indexes/no-auth.md")],
                ["apiKey", stats["api_key"], link("Browse", "generated/indexes/api-key.md")],
                ["OAuth", stats["oauth"], link("Browse", "generated/indexes/oauth.md")],
                ["X-Mashape-Key", stats["mashape"], link("Browse", "generated/indexes/mashape.md")],
                ["User-Agent", stats["user_agent"], link("Browse", "generated/indexes/user-agent.md")],
            ],
        ),
        "",
        "> **Note:** Auth = `No` means the catalog lists no authentication. Registration or API keys may still be required in practice.",
        "",
        "## Discovery by use case",
        "",
        "Curated filters with documented criteria — not rankings, not sponsored placements.",
        "",
        *use_case_lines,
        "## Developer score",
        "",
        "A transparent, optional signal. Unknown fields contribute 0. This is **not** a popularity ranking.",
        "",
        table(
            ["Signal", "Points"],
            [
                ["HTTPS = Yes", "+1"],
                ["CORS = Yes", "+1"],
                ["Auth = No", "+2"],
                ["OpenAPI available (verified)", "+1"],
                ["Postman collection (verified)", "+1"],
                ["Official SDK (verified)", "+1"],
                ["Free or free tier (verified)", "+2"],
                ["Maximum", "11"],
            ],
        ),
        "",
        "**API health** is scored separately from link checks (reachable docs, HTTPS URL, documentation available, not dead).",
        "",
        table(
            ["Health metric", "Count"],
            [
                ["Broken links (last check)", stats["broken_links"]],
                ["Dead (3 consecutive failures)", stats["dead"]],
                ["Needs review (possible duplicates)", stats["needs_review"]],
            ],
        ),
        "",
        f"[Health index](generated/indexes/health.md) · [Duplicates](generated/indexes/duplicates.md)",
        "",
        "A single failed check never removes an API from the catalog.",
        "",
        "## Contributing & automation",
        "",
        "See [CONTRIBUTING.md](CONTRIBUTING.md). Open a pull request to add APIs, fix metadata, or improve the catalog pipeline.",
        "",
        "| Workflow | Schedule |",
        "| --- | --- |",
        "| Pull request validation | Schema, duplicates, Markdown, and count checks |",
        "| Link health check | Daily documentation URL reachability |",
        "| Catalog sync | Weekly rebuild and update PR when data changes |",
        "",
        "## Data sources",
        "",
        table(
            ["Source", "Role"],
            [
                ["This repository", "Curated catalog (name, docs URL, description, Auth, HTTPS, CORS, category)"],
                ["Official provider documentation", "Only accepted source for verified enrichment"],
                ["Derived rules in this repo", "Browser-ready, scores, registration hints from Auth"],
            ],
        ),
        "",
        "Enrichment priority: official docs → official website → official GitHub → official terms → official OpenAPI. "
        "Third-party articles and search snippets are not authoritative.",
        "",
        "## License",
        "",
        "MIT. See [LICENSE](LICENSE).",
        "",
    ]
    return "\n".join(lines)


def render_generated_readme(stats: dict[str, Any], categories: list[dict[str, Any]]) -> str:
    rows = [
        [
            link(item["name"], f"categories/{item['slug']}.md"),
            item["count"],
            item["description"],
        ]
        for item in categories
    ]
    return "\n".join(
        [
            banner(),
            "",
            "# Generated catalog",
            "",
            "This directory is produced by `scripts/build.py`. Do not edit it by hand.",
            "",
            f"{stats['total_apis']} APIs in {stats['total_categories']} categories.",
            "",
            "- [Compact API list](APIs.md)",
            "- [No-auth index](indexes/no-auth.md)",
            "- [Browser-ready index](indexes/browser-ready.md)",
            "- [Search](indexes/search.md)",
            "- [Search index (JSON)](indexes/search.json)",
            "",
            table(["Category", "APIs", "Description"], rows),
            "",
        ]
    )


def render_apis_md(apis: list[dict[str, Any]], categories: list[dict[str, Any]]) -> str:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for api in apis:
        for name in api_categories(api):
            grouped[name].append(api)
    toc = [f"- {link(item['name'], '#' + item['slug'])} ({item['count']})" for item in categories]
    sections = []
    for item in categories:
        sections.append(f"## {item['name']}")
        sections.append("")
        sections.append(api_table(grouped[item["name"]]))
        sections.append("")
        sections.append("[Back to catalog index](README.md)")
        sections.append("")
    return "\n".join(
        [
            banner(),
            "",
            "# All APIs",
            "",
            "Compact directory grouped by category. Details and provenance live in "
            "[`data/normalized/apis.json`](../data/normalized/apis.json).",
            "",
            *toc,
            "",
            *sections,
        ]
    )


def render_category_page(item: dict[str, Any], apis: list[dict[str, Any]], related_links: list[str]) -> str:
    auth_counts = Counter(value_of(api["auth"]) for api in apis)
    https_counts = Counter(value_of(api["https"]) for api in apis)
    cors_counts = Counter(value_of(api["cors"]) for api in apis)
    related = ", ".join(related_links) if related_links else "None documented"
    return "\n".join(
        [
            banner(),
            "",
            f"# {item['name']}",
            "",
            item["description"],
            "",
            f"**{item['count']} APIs** in this category.",
            "",
            "## Breakdown",
            "",
            table(
                ["Dimension", "Yes / value", "Count"],
                [
                    ["Authentication", "No", auth_counts.get("No", 0)],
                    ["Authentication", "apiKey", auth_counts.get("apiKey", 0)],
                    ["Authentication", "OAuth", auth_counts.get("OAuth", 0)],
                    ["HTTPS", "Yes", https_counts.get("Yes", 0)],
                    ["HTTPS", "No", https_counts.get("No", 0)],
                    ["CORS", "Yes", cors_counts.get("Yes", 0)],
                    ["CORS", "No", cors_counts.get("No", 0)],
                    ["CORS", "Unknown", cors_counts.get("Unknown", 0)],
                    ["Browser ready", "Yes", item["browser_ready"]],
                ],
            ),
            "",
            "## Quick filters",
            "",
            "- [No-auth APIs](../indexes/no-auth.md)",
            "- [Browser-ready APIs](../indexes/browser-ready.md)",
            "- [HTTPS APIs](../indexes/https.md)",
            "- [CORS-enabled APIs](../indexes/cors.md)",
            "",
            "## APIs",
            "",
            api_table(sorted(apis, key=lambda item: (item["name"].lower(), item["canonical_url"]))),
            "",
            f"**Related categories:** {related}",
            "",
            "[Back to category explorer](../README.md) · [Back to repository README](../../README.md)",
            "",
        ]
    )


def render_index_page(title: str, description: str, apis: list[dict[str, Any]], criteria: str) -> str:
    return "\n".join(
        [
            banner(),
            "",
            f"# {title}",
            "",
            description,
            "",
            f"**Criteria:** `{criteria}`",
            "",
            f"**{len(apis)} APIs** match this filter. This is not a ranking.",
            "",
            api_table(
                sorted(apis, key=lambda item: (item["name"].lower(), item["canonical_url"])),
                include_category=True,
            ),
            "",
            "[Back to catalog index](../README.md) · [Back to repository README](../../README.md)",
            "",
        ]
    )


def write_indexes(apis: list[dict[str, Any]]) -> None:
    INDEXES_DIR.mkdir(parents=True, exist_ok=True)
    filters = [
        (
            "no-auth.md",
            "APIs with no authentication",
            "Auth = No",
            [api for api in apis if value_of(api["auth"]) == "No"],
            "Catalog Auth field is No. Registration may still be required.",
        ),
        (
            "api-key.md",
            "APIs using an API key",
            "Auth = apiKey",
            [api for api in apis if value_of(api["auth"]) == "apiKey"],
            "Catalog Auth field is apiKey. Key location (header vs query) is Unknown.",
        ),
        (
            "oauth.md",
            "APIs using OAuth",
            "Auth = OAuth",
            [api for api in apis if value_of(api["auth"]) == "OAuth"],
            "Catalog Auth field is OAuth.",
        ),
        (
            "mashape.md",
            "APIs using X-Mashape-Key",
            "Auth = X-Mashape-Key",
            [api for api in apis if value_of(api["auth"]) == "X-Mashape-Key"],
            "Catalog Auth field is X-Mashape-Key.",
        ),
        (
            "user-agent.md",
            "APIs requiring a User-Agent",
            "Auth = User-Agent",
            [api for api in apis if value_of(api["auth"]) == "User-Agent"],
            "Catalog Auth field is User-Agent.",
        ),
        (
            "browser-ready.md",
            "Browser-ready APIs",
            "HTTPS = Yes AND CORS = Yes",
            [api for api in apis if value_of(api["browser_ready"]) == "Yes"],
            "Derived from catalog HTTPS and CORS fields. HTTPS alone is not sufficient.",
        ),
        (
            "https.md",
            "HTTPS APIs",
            "HTTPS = Yes",
            [api for api in apis if value_of(api["https"]) == "Yes"],
            "Catalog HTTPS field is Yes.",
        ),
        (
            "cors.md",
            "CORS-enabled APIs",
            "CORS = Yes",
            [api for api in apis if value_of(api["cors"]) == "Yes"],
            "Catalog CORS field is Yes.",
        ),
        (
            "prototyping.md",
            "APIs for prototyping and students",
            "Auth = No AND HTTPS = Yes",
            [
                api
                for api in apis
                if value_of(api["auth"]) == "No" and value_of(api["https"]) == "Yes"
            ],
            "Low-friction filter from catalog fields only. Free-tier status is Unknown.",
        ),
        (
            "needs-review.md",
            "APIs flagged for review",
            "needs_review = true",
            [api for api in apis if api.get("needs_review")],
            "Possible duplicates or other review flags. Entries are preserved.",
        ),
        (
            "free.md",
            "Verified free APIs",
            "free_access is Free or Free Tier",
            [
                api
                for api in apis
                if value_of(api.get("free_access")) in {"Free", "Free Tier", "Open"}
            ],
            "Only APIs whose free access was later verified. Presence in the catalog is not treated as proof of a free tier.",
        ),
        (
            "rest.md",
            "Verified REST APIs",
            "api_type = REST",
            [api for api in apis if "REST" in str(value_of(api.get("api_type")))],
            "API type is Unknown unless verified from official documentation.",
        ),
        (
            "graphql.md",
            "Verified GraphQL APIs",
            "api_type contains GraphQL",
            [api for api in apis if "GraphQL" in str(value_of(api.get("api_type")))],
            "API type is Unknown unless verified from official documentation.",
        ),
        (
            "openapi.md",
            "APIs with verified OpenAPI specs",
            "openapi_available = Yes",
            [api for api in apis if value_of(api.get("openapi_available")) in {True, "Yes"}],
            "OpenAPI availability is Unknown unless an official spec URL is recorded.",
        ),
        (
            "postman.md",
            "APIs with verified Postman collections",
            "postman_available = Yes",
            [api for api in apis if value_of(api.get("postman_available")) in {True, "Yes"}],
            "Postman collections are listed only when an official public collection URL is recorded.",
        ),
    ]

    use_cases = read_yaml(USE_CASES_YML) or {}
    for key in ("ai", "saas"):
        case = use_cases.get(key) or {}
        names = set(case.get("categories") or [])
        matched = [api for api in apis if api["category"] in names]
        filters.append(
            (
                case.get("index", f"{key}.md"),
                case.get("title", key),
                case.get("criteria_text", ""),
                matched,
                case.get("description", ""),
            )
        )

    for filename, title, criteria, matched, description in filters:
        write_text(INDEXES_DIR / filename, render_index_page(title, description, matched, criteria))

    health = read_json(LINK_HEALTH_JSON, default={}) or {}
    results = health.get("results") or {}
    health_rows = []
    for api in apis:
        result = results.get(api["id"]) or {}
        health_rows.append(
            [
                link(api["name"], value_of(api["documentation_url"], api["canonical_url"])),
                api["category"],
                api.get("lifecycle_status", "Unknown"),
                result.get("classification", "Unknown"),
                score_text(api, "health_score"),
            ]
        )
    write_text(
        INDEXES_DIR / "health.md",
        "\n".join(
            [
                banner(),
                "",
                "# API health",
                "",
                "Health is based on documentation URL reachability. A single failure does not remove an API. "
                "Dead requires three consecutive failed daily checks.",
                "",
                f"Last link check: {health.get('checked_at') or 'Not run'}",
                "",
                table(
                    ["API", "Category", "Lifecycle", "Link status", "Health score"],
                    health_rows,
                ),
                "",
                "[Back to catalog index](../README.md)",
                "",
            ]
        ),
    )

    duplicates = read_json(DUPLICATES_JSON, default={"items": []}) or {"items": []}
    dup_rows = [
        [item["left_name"], item["right_name"], item["reason"], item["detail"]]
        for item in duplicates.get("items") or []
    ]
    write_text(
        INDEXES_DIR / "duplicates.md",
        "\n".join(
            [
                banner(),
                "",
                "# Possible duplicates",
                "",
                "Ambiguous pairs are flagged for review and are not merged automatically.",
                "",
                table(["API", "Other API", "Reason", "Detail"], dup_rows)
                if dup_rows
                else "No duplicate flags.",
                "",
                "[Back to catalog index](../README.md)",
                "",
            ]
        ),
    )

    search = [
        {
            "id": api["id"],
            "name": api["name"],
            "slug": api["slug"],
            "category": api["category"],
            "tags": api.get("tags") or [],
            "description": api["description"],
            "authentication": value_of(api["auth"]),
            "https": value_of(api["https"]),
            "cors": value_of(api["cors"]),
            "browser_ready": value_of(api["browser_ready"]),
            "documentation_url": value_of(api["documentation_url"]),
            "features": [
                value_of(api["auth"]),
                value_of(api["https"]),
                value_of(api["cors"]),
            ],
        }
        for api in apis
    ]
    write_json(INDEXES_DIR / "search.json", search)
    write_text(
        INDEXES_DIR / "search.md",
        "\n".join(
            [
                banner(),
                "",
                "# Search index",
                "",
                "Every API is indexed by name, slug, category, tags, description, authentication, and feature flags.",
                "",
                "Machine-readable index: [search.json](search.json)",
                "",
                "Example queries this index is designed to support:",
                "",
                "- `weather`",
                "- `free weather API` (free access is Unknown unless verified)",
                "- `no auth weather`",
                "- `CORS weather`",
                "- `finance REST API` (API type is Unknown unless verified)",
                "- `OAuth social APIs`",
                "",
                "On GitHub, use the repository search box over `generated/` and `data/normalized/apis.json`.",
                "",
                "## Filter indexes",
                "",
                "- [No auth](no-auth.md)",
                "- [API key](api-key.md)",
                "- [OAuth](oauth.md)",
                "- [Browser ready](browser-ready.md)",
                "- [HTTPS](https.md)",
                "- [CORS](cors.md)",
                "- [Prototyping](prototyping.md)",
                "- [Verified free](free.md)",
                "- [REST](rest.md)",
                "- [GraphQL](graphql.md)",
                "- [OpenAPI](openapi.md)",
                "- [Postman](postman.md)",
                "",
                "[Back to catalog index](../README.md)",
                "",
            ]
        ),
    )


def generate_docs() -> dict[str, Any]:
    apis = load_apis()
    upstream = read_json(UPSTREAM_JSON, default={}) or {}
    stats = compute_stats(
        apis,
        extras={
            "catalog_build": upstream.get("commit_sha"),
            "catalog_fetched_at": upstream.get("fetched_at"),
        },
    )
    categories = category_breakdown(apis)
    write_json(STATS_JSON, stats)
    write_json(CATEGORIES_JSON, {"categories": categories})

    write_text(ROOT_README, render_root_readme(apis, stats, categories))
    write_text(GENERATED_README, render_generated_readme(stats, categories))
    write_text(GENERATED_APIS, render_apis_md(apis, categories))

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for api in apis:
        for name in api_categories(api):
            grouped[name].append(api)
    slug_for = {item["name"]: item["slug"] for item in categories}
    for item in categories:
        related_links = []
        for name in item.get("related") or []:
            slug = slug_for.get(name)
            if slug:
                related_links.append(link(name, f"{slug}.md"))
        write_text(
            CATEGORIES_DIR / f"{item['slug']}.md",
            render_category_page(item, grouped[item["name"]], related_links),
        )

    write_indexes(apis)
    return stats


def main() -> int:
    stats = generate_docs()
    print(f"Generated documentation for {stats['total_apis']} APIs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
