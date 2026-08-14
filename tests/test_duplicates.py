from api_directory.deduplicate import detect_duplicates, duplicate_canonical_urls
from api_directory.fields import canonical_url, normalize_provider_name
from api_directory.normalize import normalize_entries
from api_directory.parse import parse_readme


def test_canonical_url_strips_utm_and_trailing_slash():
    url = "https://alexwohlbruck.github.io/cat-facts/?utm_source=Github&utm_medium=Referral"
    assert canonical_url(url) == "https://alexwohlbruck.github.io/cat-facts"


def test_duplicate_display_names_are_flagged_not_merged(sample_markdown):
    parsed = parse_readme(sample_markdown)
    apis = normalize_entries(parsed["entries"])
    flags = detect_duplicates(apis)
    cat_flags = [
        item
        for item in flags
        if item["left_name"] == "Cat Facts" and item["right_name"] == "Cat Facts"
    ]
    assert cat_flags
    assert len([api for api in apis if api["name"] == "Cat Facts"]) == 2
    assert duplicate_canonical_urls(apis) == []


def test_normalized_provider_name_collapses_suffixes():
    assert normalize_provider_name("Example API") == normalize_provider_name("ExampleAPI")
    assert normalize_provider_name("Example API Service") == "example"


def test_same_canonical_url_is_a_hard_duplicate(sample_markdown):
    parsed = parse_readme(sample_markdown)
    apis = normalize_entries(parsed["entries"])
    clone = dict(apis[0])
    clone["id"] = "clone"
    clone["name"] = "Clone"
    apis.append(clone)
    assert duplicate_canonical_urls(apis) == [apis[0]["canonical_url"]]


def test_same_docs_url_in_two_categories_merges():
    entries = [
        {
            "name": "Example",
            "documentation_url": "https://example.com/docs",
            "description": "Example service",
            "auth": "No",
            "https": "Yes",
            "cors": "Yes",
            "category": "Animals",
            "line_number": 1,
        },
        {
            "name": "Example",
            "documentation_url": "https://example.com/docs",
            "description": "Example service",
            "auth": "No",
            "https": "Yes",
            "cors": "Yes",
            "category": "Weather",
            "line_number": 2,
        },
    ]
    apis = normalize_entries(entries)
    assert len(apis) == 1
    assert apis[0]["category"] == "Animals"
    assert apis[0]["secondary_categories"] == ["Weather"]
    assert duplicate_canonical_urls(apis) == []
