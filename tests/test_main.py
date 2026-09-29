# -*- coding: utf-8 -*-
"""main（MCP 工具层）单元测试：工具注册、四工具行为分支。全部 monkeypatch，零真网。"""
import asyncio
import json

import pytest

from wop_mcp import main as wop_main
from wop_mcp import doc_center, http_utils

SAMPLE_INDEX = """\
## 灵活用工（staffing）

- [开票申请](staffing/api/staffing/open/v1/invoice/apply.20260922233115293.md)：按项目提交开票申请 — `POST /staffing/open/v1/invoice/apply` · 能力：灵活用工转账交易能力
- [开票查询](staffing/api/staffing/open/v1/invoice/query.20260922233120255.md)：查询申请状态 — `POST /staffing/open/v1/invoice/query` · 能力：灵活用工转账交易能力
"""

FAKE_DETAIL = "# 开票申请（v1）\n\n## 请求参数\n| 参数 | 类型 |\n|---|---|"


@pytest.fixture(autouse=True)
def _reset_index_cache():
    doc_center.reset_cache()
    yield
    doc_center.reset_cache()


@pytest.fixture()
def fake_index(monkeypatch):
    def fake_fetch(force=False):
        entries = doc_center.parse_llms_index(SAMPLE_INDEX, "https://cdn.example.com")
        return entries, SAMPLE_INDEX

    monkeypatch.setattr(wop_main, "fetch_index", fake_fetch)


def test_four_tools_registered():
    tools = asyncio.run(wop_main.mcp.list_tools())
    names = {tool.name for tool in tools}
    assert names == {
        "wop_overview",
        "wop_api_detail",
        "wop_link_detail",
        "wop_gen_key_pair",
    }
    assert all(tool.description for tool in tools)


def test_overview_returns_preamble_plus_index(fake_index):
    result = wop_main.wop_overview()
    assert "三步接入" in result
    assert "开票申请" in result


def test_overview_download_error_returns_string(monkeypatch):
    def fake_fetch(force=False):
        raise http_utils.DownloadError("HTTP 请求失败 url=x 原因=y")

    monkeypatch.setattr(wop_main, "fetch_index", fake_fetch)
    result = wop_main.wop_overview()
    assert result.startswith("HTTP 请求失败")


def test_api_detail_by_path(fake_index, monkeypatch):
    captured = {}

    def fake_download(url, timeout=None):
        captured["url"] = url
        return FAKE_DETAIL

    monkeypatch.setattr(wop_main.http_utils, "download_content", fake_download)
    result = wop_main.wop_api_detail("/staffing/open/v1/invoice/apply")
    assert result == FAKE_DETAIL
    assert captured["url"].endswith(
        "/staffing/api/staffing/open/v1/invoice/apply.20260922233115293.md"
    )


def test_api_detail_by_url_passthrough(monkeypatch):
    captured = {}

    def fake_download(url, timeout=None):
        captured["url"] = url
        return FAKE_DETAIL

    monkeypatch.setattr(wop_main.http_utils, "download_content", fake_download)
    result = wop_main.wop_api_detail("https://cdn.example.com/anything.md")
    assert result == FAKE_DETAIL
    assert captured["url"] == "https://cdn.example.com/anything.md"


def test_api_detail_ambiguous_returns_candidates(fake_index, monkeypatch):
    monkeypatch.setattr(
        wop_main, "resolve_api", _ambiguous_stub
    )
    result = wop_main.wop_api_detail("invoice")
    assert "匹配到多个接口" in result
    assert "开票申请" in result and "开票查询" in result


def _ambiguous_stub(query, entries):
    raise doc_center.ApiAmbiguousError(entries[:2])


def test_api_detail_not_found_lists_all(fake_index):
    result = wop_main.wop_api_detail("/no/such/api")
    assert "未匹配到接口" in result
    assert "开票申请" in result and "开票查询" in result


def test_api_detail_empty_input(fake_index):
    result = wop_main.wop_api_detail("  ")
    assert "api 参数为空" in result


def test_api_detail_index_download_error(monkeypatch):
    def fake_fetch(force=False):
        raise http_utils.DownloadError("HTTP 请求失败 url=x 原因=y")

    monkeypatch.setattr(wop_main, "fetch_index", fake_fetch)
    result = wop_main.wop_api_detail("/staffing/open/v1/invoice/apply")
    assert result.startswith("HTTP 请求失败")


def test_api_detail_detail_download_error(fake_index, monkeypatch):
    def fake_download(url, timeout=None):
        raise http_utils.DownloadError(f"HTTP 请求失败 url={url} 原因=boom")

    monkeypatch.setattr(wop_main.http_utils, "download_content", fake_download)
    result = wop_main.wop_api_detail("/staffing/open/v1/invoice/apply")
    assert result.startswith("HTTP 请求失败")


def test_link_detail_relative_joins_base(monkeypatch):
    captured = {}

    def fake_download(url, timeout=None):
        captured["url"] = url
        return "full corpus"

    monkeypatch.setattr(wop_main.http_utils, "download_content", fake_download)
    monkeypatch.setenv("WOP_DOC_BASE_URL", "https://cdn.example.com/dc/")
    result = wop_main.wop_link_detail("llms-full.txt")
    assert result == "full corpus"
    assert captured["url"] == "https://cdn.example.com/dc/llms-full.txt"


def test_link_detail_full_url_and_empty(monkeypatch):
    captured = {}

    def fake_download(url, timeout=None):
        captured["url"] = url
        return "page"

    monkeypatch.setattr(wop_main.http_utils, "download_content", fake_download)
    assert wop_main.wop_link_detail("https://other.example.com/x.md") == "page"
    assert captured["url"] == "https://other.example.com/x.md"
    assert "url 参数为空" in wop_main.wop_link_detail("")


def test_link_detail_download_error(monkeypatch):
    def fake_download(url, timeout=None):
        raise http_utils.DownloadError("HTTP 请求失败 url=x 原因=y")

    monkeypatch.setattr(wop_main.http_utils, "download_content", fake_download)
    assert wop_main.wop_link_detail("whatever.md").startswith("HTTP 请求失败")


def test_gen_key_pair_tool_end_to_end(monkeypatch, tmp_path):
    monkeypatch.setenv("WOP_KEYS_DIR", str(tmp_path))
    result = wop_main.wop_gen_key_pair("SM2")
    assert set(result.keys()) == set(keypair_result_keys())
    assert "BEGIN" not in json.dumps(result)
    with pytest.raises(ValueError, match="不支持的算法"):
        wop_main.wop_gen_key_pair("RSA4096")


def keypair_result_keys():
    from wop_mcp.keypair import RESULT_KEYS
    return RESULT_KEYS


def test_cli_help_prints_usage_and_exits_zero(capsys, monkeypatch):
    monkeypatch.setattr("sys.argv", ["wop-mcp", "--help"])
    with pytest.raises(SystemExit) as exc:
        wop_main.main()
    assert exc.value.code == 0
    assert "usage: wop-mcp" in capsys.readouterr().out


def test_cli_version_prints_version(capsys, monkeypatch):
    monkeypatch.setattr("sys.argv", ["wop-mcp", "--version"])
    with pytest.raises(SystemExit) as exc:
        wop_main.main()
    assert exc.value.code == 0
    assert f"wop-mcp {wop_main.__version__}" in capsys.readouterr().out
