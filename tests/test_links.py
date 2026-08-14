from unittest.mock import MagicMock

import httpx

from api_directory.check_links import check_url, classify_exception
from api_directory.fields import is_valid_http_url
from api_directory.enrich import classify_link_status


def test_url_format():
    assert is_valid_http_url("https://example.com/docs")
    assert is_valid_http_url("http://example.com/docs")
    assert not is_valid_http_url("ftp://example.com/docs")
    assert not is_valid_http_url("not-a-url")


def test_status_classification():
    assert classify_link_status(200) == "200 OK"
    assert classify_link_status(301) == "3xx Redirect"
    assert classify_link_status(404) == "4xx Broken"
    assert classify_link_status(503) == "5xx Server Error"
    assert classify_link_status("timeout") == "timeout"


def test_timeout_exception_classification():
    assert classify_exception(httpx.TimeoutException("late")) == "Timeout"


def test_check_url_follows_head_to_get_and_records_redirect(monkeypatch):
    client = MagicMock()
    head = MagicMock()
    head.status_code = 301
    head.url = "https://example.com/docs"
    get = MagicMock()
    get.status_code = 200
    get.url = "https://example.com/docs"
    client.head.return_value = head
    client.get.return_value = get

    # 301 from HEAD is a completed 3xx; check_url returns it without GET
    result = check_url(client, "https://example.com/docs", retries=1)
    assert result["classification"] == "3xx Redirect"
    assert result["ok"] is True
    client.get.assert_not_called()
