# -*- coding: utf-8 -*-
"""doc_center 单元测试：索引解析、查询归一化、三级匹配、缓存、overview 装配。"""
import pytest

from wop_mcp import config, doc_center, http_utils

BASE = "https://assets.example.com/doc-center"

SAMPLE_INDEX = """\
# 万联易达开放平台 API 文档

> 说明行应被跳过

## 灵活用工（staffing）

- [开票申请](staffing/api/staffing/open/v1/invoice/apply.20260922233115293.md)：按项目提交开票申请，幂等键 companyId+outTradeNo — `POST /staffing/open/v1/invoice/apply` · 能力：灵活用工转账交易能力
- [转账提交](staffing/api/staffing/open/v1/payment/apply.20260922233125402.md)：批量发放灵工服务费 — `POST /staffing/open/v1/payment/apply` · 能力：灵活用工转账交易能力
- [回单查询B](mock/api/mock/v1/receipt/query.20260922233140334.md)：批量查询转账回单 — `POST /mock/v1/receipt/query` · 能力：测试能力

## 通用中台基础能力业务域（tyztjcnl）

- [分页查询法定节假日](tyztjcnl/api/tyztjcnl/v4/mdm/holiday/page.20260924111756449.md)：分页查询法定节假日 — `POST /tyztjcnl/v4/mdm/holiday/page` · 能力：节假日查询接口
- [非 API 普通链接](some/guide.md)：无方法标记的行应被跳过
"""


@pytest.fixture()
def entries():
    return doc_center.parse_llms_index(SAMPLE_INDEX, BASE)


def test_parse_extracts_fields_and_skips_non_api_lines(entries):
    assert len(entries) == 4
    first = entries[0]
    assert first.domain == "灵活用工（staffing）"
    assert first.title == "开票申请"
    assert (
        first.url
        == BASE + "/staffing/api/staffing/open/v1/invoice/apply.20260922233115293.md"
    )
    assert first.method == "POST"
    assert first.api_path == "/staffing/open/v1/invoice/apply"
    assert first.capability == "灵活用工转账交易能力"
    assert first.description.startswith("按项目提交开票申请")
    assert entries[3].domain == "通用中台基础能力业务域（tyztjcnl）"


def test_resolve_exact_path(entries):
    entry = doc_center.resolve_api("/staffing/open/v1/invoice/apply", entries)
    assert entry.title == "开票申请"


def test_resolve_method_prefix_and_backticks(entries):
    entry = doc_center.resolve_api("`POST /staffing/open/v1/payment/apply`", entries)
    assert entry.title == "转账提交"
    entry = doc_center.resolve_api("post /staffing/open/v1/payment/apply", entries)
    assert entry.title == "转账提交"


def test_resolve_path_without_leading_slash_and_suffix_displacement(entries):
    # 前缀错位陷阱：文档体内路径 /open/v1/… 应后缀匹配索引路径 /staffing/open/v1/…
    entry = doc_center.resolve_api("open/v1/invoice/apply", entries)
    assert entry.title == "开票申请"


def test_resolve_ambiguous_suffix_raises(entries):
    # /v1/receipt/query 后缀同时命中 /mock/v1/... 与另一条时才歧义；此处仅一条
    entry = doc_center.resolve_api("/v1/receipt/query", entries)
    assert entry.title == "回单查询B"


def test_resolve_ambiguous_title_raises_with_candidates(entries):
    with pytest.raises(doc_center.ApiAmbiguousError) as exc_info:
        doc_center.resolve_api("查询", entries)
    titles = {e.title for e in exc_info.value.candidates}
    assert len(titles) >= 2


def test_resolve_not_found_raises(entries):
    with pytest.raises(doc_center.ApiNotFoundError):
        doc_center.resolve_api("/no/such/api", entries)


def test_resolve_empty_query_raises(entries):
    with pytest.raises(doc_center.ApiNotFoundError):
        doc_center.resolve_api("   ", entries)


def test_normalize_query_variants():
    assert doc_center.normalize_query("  `/a/b ` ") == "/a/b"
    assert doc_center.normalize_query("POST /a/b") == "/a/b"
    assert doc_center.normalize_query("get  /a/b/") == "/a/b"
    assert doc_center.normalize_query("转账提交") == "转账提交"
    assert doc_center.normalize_query("") == ""


def test_overview_markdown_preamble_plus_index():
    result = doc_center.overview_markdown(SAMPLE_INDEX)
    assert result.startswith("# 万联易达开放平台（WOP）接入指南")
    assert "三步接入" in result
    assert "wop_gen_key_pair" in result
    assert "WOP-SM2-SM3" in result
    assert SAMPLE_INDEX.splitlines()[-2] in result  # 索引原文完整保留


def test_fetch_index_caches_within_ttl(monkeypatch):
    doc_center.reset_cache()
    calls = []

    def fake_download(url, timeout=None):
        calls.append(url)
        return SAMPLE_INDEX

    monkeypatch.setattr(doc_center.http_utils, "download_content", fake_download)
    monkeypatch.setenv("WOP_DOC_BASE_URL", BASE)
    entries1, text1 = doc_center.fetch_index()
    entries2, text2 = doc_center.fetch_index()
    assert len(calls) == 1
    assert text1 == text2
    assert entries1 == entries2
    assert calls[0] == BASE + "/llms.txt"


def test_fetch_index_ttl_zero_disables_cache(monkeypatch):
    doc_center.reset_cache()
    calls = []

    def fake_download(url, timeout=None):
        calls.append(1)
        return SAMPLE_INDEX

    monkeypatch.setattr(doc_center.http_utils, "download_content", fake_download)
    monkeypatch.setenv("WOP_DOC_BASE_URL", BASE)
    monkeypatch.setenv("WOP_INDEX_CACHE_TTL", "0")
    doc_center.fetch_index()
    doc_center.fetch_index()
    assert len(calls) == 2


def test_fetch_index_force_bypasses_cache(monkeypatch):
    doc_center.reset_cache()
    calls = []

    def fake_download(url, timeout=None):
        calls.append(1)
        return SAMPLE_INDEX

    monkeypatch.setattr(doc_center.http_utils, "download_content", fake_download)
    monkeypatch.setenv("WOP_DOC_BASE_URL", BASE)
    doc_center.fetch_index()
    doc_center.fetch_index(force=True)
    assert len(calls) == 2


def test_fetch_index_propagates_download_error(monkeypatch):
    doc_center.reset_cache()
    monkeypatch.setenv("WOP_DOC_BASE_URL", BASE)

    def fake_download(url, timeout=None):
        raise http_utils.DownloadError("HTTP 请求失败 url=x 原因=y")

    monkeypatch.setattr(doc_center.http_utils, "download_content", fake_download)
    with pytest.raises(http_utils.DownloadError):
        doc_center.fetch_index()


def test_config_env_overrides(monkeypatch):
    monkeypatch.setenv("WOP_DOC_BASE_URL", "https://cdn.example.com/base/")
    assert config.doc_base_url() == "https://cdn.example.com/base"
    monkeypatch.setenv("WOP_INDEX_CACHE_TTL", "bad")
    assert config.index_cache_ttl_seconds() == config.DEFAULT_INDEX_CACHE_TTL_SECONDS
