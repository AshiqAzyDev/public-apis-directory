from api_directory.normalize import normalize_entries
from api_directory.parse import parse_readme
from api_directory.validate import validate_apis


def _sample_apis(markdown: str):
    parsed = parse_readme(markdown)
    return normalize_entries(parsed["entries"])


def test_required_fields_and_enums(sample_markdown):
    apis = _sample_apis(sample_markdown)
    errors = validate_apis(apis, min_count=1)
    assert errors == []
    for api in apis:
        assert api["name"]
        assert api["description"]
        assert api["category"]
        assert api["documentation_url"]["value"].startswith("http")


def test_invalid_auth_is_rejected(invalid_auth_markdown):
    parsed = parse_readme(invalid_auth_markdown)
    apis = normalize_entries(parsed["entries"])
    errors = validate_apis(apis, min_count=1)
    assert any("invalid Auth" in error for error in errors)


def test_minimum_count_failure(sample_markdown):
    apis = _sample_apis(sample_markdown)
    errors = validate_apis(apis, min_count=1000)
    assert any("minimum is 1000" in error for error in errors)
