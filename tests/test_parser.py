from api_directory.parse import parse_readme


def test_parser_skips_promotional_section_and_reads_index_categories(sample_markdown):
    parsed = parse_readme(sample_markdown)
    assert parsed["categories"] == ["Animals", "Weather"]
    names = {entry["name"] for entry in parsed["entries"]}
    assert "IPstack" not in names
    assert parsed["count"] == 5


def test_parser_reads_table_rows_and_extra_cells(sample_markdown):
    parsed = parse_readme(sample_markdown)
    first = next(entry for entry in parsed["entries"] if "alexwohlbruck" in entry["documentation_url"])
    assert first["name"] == "Cat Facts"
    assert first["auth"] == "No"
    assert first["https"] == "Yes"
    assert first["cors"] == "No"
    assert first["category"] == "Animals"


def test_parser_strips_auth_backticks(sample_markdown):
    parsed = parse_readme(sample_markdown)
    weather = next(entry for entry in parsed["entries"] if entry["name"] == "OpenWeatherMap")
    assert weather["auth"] == "apiKey"


def test_parser_keeps_duplicate_display_names_with_different_urls(sample_markdown):
    parsed = parse_readme(sample_markdown)
    cats = [entry for entry in parsed["entries"] if entry["name"] == "Cat Facts"]
    assert len(cats) == 2
    urls = {entry["documentation_url"] for entry in cats}
    assert len(urls) == 2
