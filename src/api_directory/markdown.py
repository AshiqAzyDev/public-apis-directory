"""Markdown helpers for GitHub-native generated docs."""

from __future__ import annotations

from typing import Any, Iterable

from api_directory.fields import value_of
from api_directory.paths import BANNER


def cell(text: Any) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ").strip()


def table(headers: list[str], rows: Iterable[list[Any]]) -> str:
    head = "| " + " | ".join(headers) + " |"
    sep = "| " + " | ".join("---" for _ in headers) + " |"
    body = ["| " + " | ".join(cell(col) for col in row) + " |" for row in rows]
    return "\n".join([head, sep, *body])


def banner() -> str:
    return BANNER


def link(label: str, url: str) -> str:
    return f"[{cell(label)}]({url})"


def field_text(api: dict[str, Any], key: str, default: str = "Unknown") -> str:
    value = value_of(api.get(key), default)
    if value is None or value == []:
        return "Unknown"
    if isinstance(value, list):
        return ", ".join(str(item) for item in value) or "Unknown"
    return str(value)


def score_text(api: dict[str, Any], key: str = "developer_score") -> str:
    score = api.get(key) or {}
    value = score.get("value")
    maximum = score.get("max")
    if value is None or maximum is None:
        return "Unknown"
    return f"{value}/{maximum}"
