"""Provenance field helpers, slugs, and URL canonicalization."""

from __future__ import annotations

import hashlib
import re
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

SOURCE_PUBLIC_APIS = "public-apis"
SOURCE_PROVIDER = "provider_documentation"
SOURCE_DERIVED = "derived"
SOURCE_UNKNOWN = "unknown"
SOURCE_LINK_CHECK = "link-check"


def field(
    value: Any,
    source_type: str,
    source_url: str | None = None,
    verified_at: str | None = None,
) -> dict[str, Any]:
    return {
        "value": value,
        "source_type": source_type,
        "source_url": source_url,
        "verified_at": verified_at,
    }


def unknown_field(value: Any = "Unknown") -> dict[str, Any]:
    return field(value, SOURCE_UNKNOWN)


def derived_field(value: Any) -> dict[str, Any]:
    return field(value, SOURCE_DERIVED)


def upstream_field(value: Any) -> dict[str, Any]:
    return field(value, SOURCE_PUBLIC_APIS)


def value_of(obj: Any, default: Any = None) -> Any:
    if isinstance(obj, dict) and "value" in obj:
        return obj["value"]
    return default if obj is None else obj


def slugify(text: str) -> str:
    lowered = text.lower().replace("&", "and")
    slug = re.sub(r"[^a-z0-9]+", "-", lowered)
    return slug.strip("-") or "item"


def category_slug(name: str) -> str:
    return slugify(name)


def canonical_url(url: str) -> str:
    parsed = urlparse(url.strip())
    scheme = (parsed.scheme or "https").lower()
    netloc = parsed.netloc.lower()
    if netloc.startswith("www."):
        host = netloc
    else:
        host = netloc
    query_pairs = [
        (key, val)
        for key, val in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.lower().startswith("utm_")
    ]
    path = parsed.path.rstrip("/")
    return urlunparse((scheme, host, path, "", urlencode(query_pairs), ""))


def provider_domain(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def make_id(name: str, canonical: str) -> str:
    digest = hashlib.sha1(canonical.encode("utf-8")).hexdigest()[:8]
    return f"{slugify(name)}-{digest}"


def normalize_provider_name(name: str) -> str:
    compact = re.sub(r"[^a-z0-9]", "", name.lower())
    compact = re.sub(r"^the", "", compact)
    while True:
        stripped = re.sub(r"(api|service|inc|llc|ltd)$", "", compact)
        if stripped == compact:
            break
        compact = stripped
    return compact


def is_valid_http_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
