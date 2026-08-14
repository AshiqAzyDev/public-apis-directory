from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def read_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


@pytest.fixture
def sample_markdown() -> str:
    return read_fixture("sample_readme.md")


@pytest.fixture
def invalid_auth_markdown() -> str:
    return read_fixture("invalid_auth.md")
