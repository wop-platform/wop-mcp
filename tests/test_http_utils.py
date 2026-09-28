# -*- coding: utf-8 -*-
"""http_utils 单元测试：成功、重试、耗尽、配置默认超时。全部 monkeypatch，零真网。"""
import urllib.error

import pytest

from wop_mcp import http_utils


class _FakeResponse:
    def __init__(self, payload: bytes):
        self._payload = payload

    def read(self) -> bytes:
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


def test_download_success_sends_ua_and_returns_text(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["ua"] = request.get_header("User-agent")
        return _FakeResponse("你好 WOP".encode("utf-8"))

    monkeypatch.setattr(http_utils.urllib.request, "urlopen", fake_urlopen)
    text = http_utils.download_content("https://example.com/a.md", timeout=3.0)
    assert text == "你好 WOP"
    assert captured["url"] == "https://example.com/a.md"
    assert captured["timeout"] == 3.0
    assert captured["ua"].startswith("wop-mcp/")


def test_download_retries_once_then_succeeds(monkeypatch):
    attempts = []

    def fake_urlopen(request, timeout):
        attempts.append(1)
        if len(attempts) == 1:
            raise urllib.error.URLError("transient")
        return _FakeResponse(b"ok")

    monkeypatch.setattr(http_utils.urllib.request, "urlopen", fake_urlopen)
    assert http_utils.download_content("https://example.com/b.md") == "ok"
    assert len(attempts) == 2


def test_download_error_after_retries_carries_url(monkeypatch):
    def fake_urlopen(request, timeout):
        raise urllib.error.HTTPError(
            url="x", code=404, msg="Not Found", hdrs=None, fp=None
        )

    monkeypatch.setattr(http_utils.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(http_utils.DownloadError) as exc_info:
        http_utils.download_content("https://example.com/missing.md")
    assert "https://example.com/missing.md" in str(exc_info.value)
    assert "404" in str(exc_info.value)


def test_default_timeout_reads_env(monkeypatch):
    monkeypatch.setenv("WOP_HTTP_TIMEOUT", "7.5")
    captured = {}

    def fake_urlopen(request, timeout):
        captured["timeout"] = timeout
        return _FakeResponse(b"ok")

    monkeypatch.setattr(http_utils.urllib.request, "urlopen", fake_urlopen)
    http_utils.download_content("https://example.com/c.md")
    assert captured["timeout"] == 7.5


def test_invalid_env_timeout_falls_back(monkeypatch):
    monkeypatch.setenv("WOP_HTTP_TIMEOUT", "not-a-number")
    captured = {}

    def fake_urlopen(request, timeout):
        captured["timeout"] = timeout
        return _FakeResponse(b"ok")

    monkeypatch.setattr(http_utils.urllib.request, "urlopen", fake_urlopen)
    http_utils.download_content("https://example.com/d.md")
    assert captured["timeout"] == http_utils.config.DEFAULT_HTTP_TIMEOUT_SECONDS
