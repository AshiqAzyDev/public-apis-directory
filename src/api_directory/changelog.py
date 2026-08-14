"""Generate changelog entries from catalog diffs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from api_directory.fields import value_of
from api_directory.io_utils import read_json, write_text
from api_directory.paths import APIS_JSON, BANNER, CHANGELOG


def utc_today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _index(apis: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {api["id"]: api for api in apis}


def diff_catalogs(
    previous: list[dict[str, Any]],
    current: list[dict[str, Any]],
) -> dict[str, list[str]]:
    before = _index(previous)
    after = _index(current)
    added = []
    removed = []
    updated = []
    moved = []

    for identifier, api in after.items():
        if identifier not in before:
            added.append(f"- {api['name']} ({api['category']})")
            continue
        old = before[identifier]
        changes: list[str] = []
        if old.get("description") != api.get("description"):
            changes.append("description changed")
        if old.get("canonical_url") != api.get("canonical_url"):
            changes.append("documentation URL changed")
        if value_of(old.get("auth")) != value_of(api.get("auth")):
            changes.append("Auth changed")
        if value_of(old.get("https")) != value_of(api.get("https")):
            changes.append("HTTPS changed")
        if value_of(old.get("cors")) != value_of(api.get("cors")):
            changes.append("CORS changed")
        if old.get("category") != api.get("category"):
            moved.append(
                f"- {api['name']} moved from {old.get('category')} to {api['category']}"
            )
        if changes:
            updated.append(f"- {api['name']} — {', '.join(changes)}")

    for identifier, api in before.items():
        if identifier not in after:
            removed.append(f"- {api['name']} ({api.get('category')})")

    return {
        "added": sorted(added),
        "removed": sorted(removed),
        "updated": sorted(updated),
        "moved": sorted(moved),
    }


def render_changelog_section(date: str, diff: dict[str, list[str]], commit: str | None) -> str:
    lines = [f"## {date}"]
    if commit:
        lines.append("")
        lines.append(f"Catalog build: `{commit[:7]}`")
    empty = True
    for heading, key in (
        ("Added", "added"),
        ("Removed", "removed"),
        ("Updated", "updated"),
        ("Category Changes", "moved"),
    ):
        items = diff.get(key) or []
        if not items:
            continue
        empty = False
        lines.append("")
        lines.append(f"### {heading}")
        lines.extend(items)
    if empty:
        lines.append("")
        lines.append("No catalog changes.")
    return "\n".join(lines) + "\n"


def write_changelog(
    previous: list[dict[str, Any]] | None,
    current: list[dict[str, Any]],
    commit: str | None,
) -> str:
    date = utc_today()
    if previous is None:
        section = (
            f"## {date}\n\n"
            f"Initial catalog: {len(current)} APIs"
            + (f" (build `{commit[:7]}`)" if commit else "")
            + ".\n"
        )
    else:
        diff = diff_catalogs(previous, current)
        if not any(diff.values()) and CHANGELOG.exists():
            return "No catalog changes."
        section = render_changelog_section(date, diff, commit)

    existing = ""
    if CHANGELOG.exists():
        existing = CHANGELOG.read_text(encoding="utf-8")
        if existing.startswith(BANNER):
            existing = existing[len(BANNER) :].lstrip("\n")
        marker = f"## {date}"
        if existing.startswith(marker):
            rest = existing.split("\n## ", 1)
            existing = "" if len(rest) == 1 else "## " + rest[1]

    header = (
        f"{BANNER}\n\n"
        "# Changelog\n\n"
        "Catalog changes tracked in this repository.\n\n"
    )
    body = section + ("\n" + existing if existing.strip() else "")
    write_text(CHANGELOG, header + body)
    return section


def previous_apis() -> list[dict[str, Any]] | None:
    payload = read_json(APIS_JSON)
    if not payload:
        return None
    return payload.get("apis")
