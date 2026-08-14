"""Validate the normalized catalog. Fail closed on data errors."""

from __future__ import annotations

from collections import Counter
from typing import Any

from jsonschema import Draft202012Validator

from api_directory.deduplicate import duplicate_canonical_urls
from api_directory.fields import is_valid_http_url, value_of
from api_directory.io_utils import read_json
from api_directory.paths import (
    APIS_JSON,
    AUTH_VALUES,
    CORS_VALUES,
    HTTPS_VALUES,
    MIN_API_COUNT,
    SCHEMA_JSON,
)


class ValidationError(Exception):
    def __init__(self, errors: list[str]) -> None:
        super().__init__("\n".join(errors))
        self.errors = errors


def validate_apis(apis: list[dict[str, Any]], min_count: int = MIN_API_COUNT) -> list[str]:
    errors: list[str] = []
    schema = read_json(SCHEMA_JSON)
    validator = Draft202012Validator(schema)

    if len(apis) < min_count:
        errors.append(f"Catalog has {len(apis)} APIs; minimum is {min_count}")

    ids: list[str] = []
    for api in apis:
        name = api.get("name") or ""
        label = name or api.get("id") or "<unknown>"
        if not name:
            errors.append("API name is missing")
        if not api.get("description"):
            errors.append(f"{label}: description is missing")
        if not api.get("category"):
            errors.append(f"{label}: category is missing")

        url = value_of(api.get("documentation_url"), api.get("canonical_url"))
        if not url or not is_valid_http_url(str(url)):
            errors.append(f"{label}: documentation URL is invalid ({url!r})")

        auth = value_of(api.get("auth"))
        if auth not in AUTH_VALUES:
            errors.append(f"{label}: invalid Auth value {auth!r}")
        https = value_of(api.get("https"))
        if https not in HTTPS_VALUES:
            errors.append(f"{label}: invalid HTTPS value {https!r}")
        cors = value_of(api.get("cors"))
        if cors not in CORS_VALUES:
            errors.append(f"{label}: invalid CORS value {cors!r}")

        for message in validator.iter_errors(api):
            errors.append(f"{label}: schema {message.message}")

        identifier = api.get("id")
        if identifier:
            ids.append(identifier)

    dup_ids = [key for key, count in Counter(ids).items() if count > 1]
    for identifier in dup_ids:
        errors.append(f"Duplicate id {identifier}")

    for url in duplicate_canonical_urls(apis):
        errors.append(f"Duplicate canonical URL {url}")

    return errors


def validate_catalog(min_count: int = MIN_API_COUNT) -> list[dict[str, Any]]:
    payload = read_json(APIS_JSON)
    if not payload:
        raise FileNotFoundError(f"Missing normalized catalog at {APIS_JSON}")
    apis = payload["apis"]
    errors = validate_apis(apis, min_count=min_count)
    if errors:
        raise ValidationError(errors)
    return apis


def main(min_count: int = MIN_API_COUNT) -> int:
    try:
        apis = validate_catalog(min_count=min_count)
    except ValidationError as exc:
        print("Validation failed:")
        for error in exc.errors[:50]:
            print(f" - {error}")
        if len(exc.errors) > 50:
            print(f" - … {len(exc.errors) - 50} more")
        return 1
    print(f"Validated {len(apis)} APIs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
