from api_directory.enrich import derive_browser_ready, enrich_apis
from api_directory.generate import category_breakdown, compute_stats, render_root_readme
from api_directory.markdown import banner
from api_directory.normalize import normalize_entries
from api_directory.parse import parse_readme
from api_directory.paths import BANNER


def _enriched_sample(markdown: str):
    parsed = parse_readme(markdown)
    return enrich_apis(normalize_entries(parsed["entries"]))


def test_browser_ready_derivation():
    assert derive_browser_ready("Yes", "Yes") == "Yes"
    assert derive_browser_ready("Yes", "No") == "No"
    assert derive_browser_ready("Yes", "Unknown") == "Unknown"
    assert derive_browser_ready("No", "Yes") == "No"


def test_generated_readme_is_stable_and_valid_markdown(sample_markdown):
    apis = _enriched_sample(sample_markdown)
    stats = compute_stats(apis, extras={"catalog_build": "abc123"})
    categories = category_breakdown(apis)
    markdown = render_root_readme(apis, stats, categories)
    assert markdown.startswith(BANNER)
    assert markdown.count("\n# ") == 1
    assert "## Category explorer" in markdown
    assert "## Start here" in markdown
    assert "## Table of contents" in markdown
    assert "## What you get" in markdown
    assert "Open-Meteo" not in markdown.split("## Category explorer")[0]
    assert str(len(apis)) in markdown
    assert banner() == BANNER
    assert markdown.count("| Category | APIs |") >= 1


def test_stats_use_generated_counts(sample_markdown):
    apis = _enriched_sample(sample_markdown)
    stats = compute_stats(apis)
    assert stats["total_apis"] == 5
    assert stats["total_categories"] == 2
    assert stats["browser_ready"] == 3
    assert stats["no_auth"] == 4
    assert stats["free"] == 0
