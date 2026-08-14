"""Parse the public-apis community catalog from README Markdown."""

from __future__ import annotations

import re
from typing import Any

from api_directory.io_utils import read_json, write_json
from api_directory.paths import PARSED_JSON, UPSTREAM_JSON

INDEX_HEADING_RE = re.compile(r"^##\s+Index\s*$", re.MULTILINE)
INDEX_ITEM_RE = re.compile(r"^\*\s+\[([^\]]+)\]\(#([^)]+)\)\s*$")
CATEGORY_HEADING_RE = re.compile(r"^###\s+(.+?)\s*$")
LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")
TABLE_ROW_RE = re.compile(r"^\|")


def _index_categories(markdown: str) -> list[str]:
    match = INDEX_HEADING_RE.search(markdown)
    if not match:
        raise ValueError("Upstream README is missing an Index section")

    names: list[str] = []
    after = markdown[match.end() :]
    for line in after.splitlines():
        if line.startswith("## ") or line.startswith("# "):
            break
        item = INDEX_ITEM_RE.match(line.strip())
        if item:
            names.append(item.group(1).strip())
    if not names:
        raise ValueError("Index section did not contain any categories")
    return names


def _split_row(line: str) -> list[str]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [cell.strip() for cell in stripped.split("|")]


def parse_readme(markdown: str) -> dict[str, Any]:
    """Return raw community-catalog entries. Skips promotional tables."""

    index_names = _index_categories(markdown)
    index_set = set(index_names)

    current_category: str | None = None
    in_catalog = False
    entries: list[dict[str, Any]] = []

    for line_number, raw_line in enumerate(markdown.splitlines(), start=1):
        heading = CATEGORY_HEADING_RE.match(raw_line)
        if heading:
            title = heading.group(1).strip()
            if title in index_set:
                current_category = title
                in_catalog = True
            else:
                current_category = None
                in_catalog = False
            continue

        if raw_line.startswith("## "):
            current_category = None
            in_catalog = False
            continue

        if not in_catalog or current_category is None:
            continue
        if not TABLE_ROW_RE.match(raw_line):
            continue
        if set(raw_line.replace("|", "").replace(":", "").replace("-", "").strip()) == set():
            continue

        cells = _split_row(raw_line)
        if len(cells) < 5:
            continue
        title_cell, description, auth, https, cors = cells[:5]
        if title_cell.lower() in {"api", "api title"}:
            continue
        if description.lower() == "description":
            continue

        link = LINK_RE.search(title_cell)
        if not link:
            continue

        entries.append(
            {
                "name": link.group(1).strip(),
                "documentation_url": link.group(2).strip(),
                "description": description.strip(),
                "auth": auth.strip().strip("`"),
                "https": https.strip(),
                "cors": cors.strip() or "Unknown",
                "category": current_category,
                "line_number": line_number,
            }
        )

    return {
        "categories": index_names,
        "entries": entries,
        "count": len(entries),
    }


def parse_upstream() -> dict[str, Any]:
    upstream = read_json(UPSTREAM_JSON)
    if not upstream or "markdown" not in upstream:
        raise FileNotFoundError(f"Missing upstream dump at {UPSTREAM_JSON}")
    parsed = parse_readme(upstream["markdown"])
    parsed["commit_sha"] = upstream.get("commit_sha")
    parsed["fetched_at"] = upstream.get("fetched_at")
    write_json(PARSED_JSON, parsed)
    return parsed


def main() -> int:
    parsed = parse_upstream()
    print(f"Parsed {parsed['count']} APIs in {len(parsed['categories'])} categories")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
