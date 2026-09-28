# -*- coding: utf-8 -*-
"""文档中心索引解析与内容装配。

WOP 文档中心为纯静态平面结构（实测 2026-09）：
- ``llms.txt``      API 索引（唯一入口，含带时间戳后缀的 .md 相对链接）
- ``llms-full.txt`` 全量语料
- ``{域}/api/{路径}.{时间戳}.md`` 各接口详情

时间戳后缀不可从 API 路径拼接，因此 ``resolve_api`` 必须经索引解析；
索引路径（staffing/api/staffing/open/v1/…）与文档体内路径（/open/v1/…）
存在前缀错位，匹配策略采用后缀匹配。
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from urllib.parse import urljoin

from . import config, http_utils

_ENTRY_RE = re.compile(r"^- \[(?P<title>[^\]]+)\]\((?P<href>[^)]+)\)：(?P<desc>.*)$")
_METHOD_PATH_RE = re.compile(r"`(?P<method>[A-Z]+)\s+(?P<path>/[^`]+)`")
_CAPABILITY_RE = re.compile(r"能力：(?P<capability>.+)$")
_METHOD_PREFIX_RE = re.compile(r"^(?:POST|GET|PUT|DELETE|PATCH)\s+", re.IGNORECASE)

# 接入指南前言（内置，随仓版本化；文档中心未来提供 guide 页后可切换为 URL 拉取）
PREAMBLE = """\
# 万联易达开放平台（WOP）接入指南

## 三步接入

1. **生成密钥对**：调用本 server 的 `wop_gen_key_pair(algorithm)`，支持 `RSA2048` / `SM2`。
   私钥只写入本地 0600 文件、不会出现在对话中；返回的 `publicKey` 可直接上报平台。
2. **上报公钥**：将 `publicKey`（§3.4 分发契约编码）配置到平台商户/应用侧。
3. **签名调用**：使用官方 SDK 对请求签名后调用 API（详见下方 SDK 列表）。

## securityReq 算法组合（crypto-strategy-spec v0.4）

| securityReq | 体系 | 说明 |
|---|---|---|
| `WOP-SM2-SM3` | 国密 | SM2 密钥 + SM3 摘要 |
| `WOP-RSA3072-SHA256` | 国际 | RSA 3072 位 |
| `WOP-RSA4096-SHA256` | 国际 | RSA 4096 位 |

> 注：本 server 密钥生成当前支持 `RSA2048` / `SM2`；国际族与国密族禁止跨族组合，
> 平台实际接受的 RSA 档位以商户中心审核为准。

## 公钥分发编码（spec §3.4，D10/D12）

- RSA 公钥：X.509 SubjectPublicKeyInfo DER 的 Base64（单行）
- SM2 公钥：未压缩点 `04‖X‖Y`（65 字节）的 Base64（单行）
- 二进制线上编码：Base64URL 无填充；十六进制统一小写

## 官方 SDK 与工具

- Python：https://github.com/wop-platform/wop-python-sdk
- Java：https://github.com/wop-platform/wop-java-sdk
- Go：https://github.com/wop-platform/wop-go-sdk
- PHP：https://github.com/wop-platform/wop-php-sdk
- .NET：https://github.com/wop-platform/wop-dotnet-sdk
- TypeScript：https://github.com/wop-platform/wop-typescript-sdk
- Agent 技能包：https://github.com/wop-platform/wop-skills

> 全量文档语料可经 `wop_link_detail` 拉取 `<基址>/llms-full.txt`。
"""


@dataclass(frozen=True)
class DocEntry:
    """llms.txt 索引中的一个 API 条目。"""

    domain: str
    title: str
    url: str
    method: str
    api_path: str
    capability: str
    description: str


class ApiAmbiguousError(Exception):
    """查询命中多个接口。"""

    def __init__(self, candidates: list[DocEntry]):
        self.candidates = candidates
        super().__init__("匹配到多个接口")


class ApiNotFoundError(Exception):
    """查询未命中任何接口。"""


def parse_llms_index(text: str, base_url: str) -> list[DocEntry]:
    """解析 llms.txt 索引文本为条目列表。

    仅收录带 `` `METHOD /path` `` 标记的 API 行，其余（目录、纯链接）跳过。
    """
    entries: list[DocEntry] = []
    domain = ""
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if line.startswith("## ") and not line.startswith("###"):
            domain = line[3:].strip()
            continue
        matched = _ENTRY_RE.match(line)
        if not matched:
            continue
        desc = matched.group("desc")
        method_path = _METHOD_PATH_RE.search(desc)
        if not method_path:
            continue
        capability_matched = _CAPABILITY_RE.search(desc)
        summary = desc.split(" — ")[0].strip()
        entries.append(
            DocEntry(
                domain=domain,
                title=matched.group("title").strip(),
                url=urljoin(base_url + "/", matched.group("href")),
                method=method_path.group("method"),
                api_path=method_path.group("path").strip(),
                capability=(
                    capability_matched.group("capability").strip()
                    if capability_matched
                    else ""
                ),
                description=summary,
            )
        )
    return entries


def normalize_query(query: str) -> str:
    """归一化查询：去空白/反引号、去方法前缀、保证以 / 开头（或保留中文名）。"""
    normalized = query.strip().strip("`").strip()
    normalized = _METHOD_PREFIX_RE.sub("", normalized).strip()
    if not normalized:
        return normalized
    if normalized.startswith("/"):
        return normalized.rstrip("/") or "/"
    return normalized


def resolve_api(query: str, entries: list[DocEntry]) -> DocEntry:
    """按 查询 → 条目 解析：精确路径 → 后缀路径 → 中文名，多命中/零命中抛异常。"""
    normalized = normalize_query(query)
    if not normalized:
        raise ApiNotFoundError("查询为空")

    exact = [e for e in entries if e.api_path == normalized]
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        raise ApiAmbiguousError(exact)

    suffix = [
        e
        for e in entries
        if e.api_path.endswith("/" + normalized.lstrip("/"))
        or (normalized.startswith("/") and e.api_path.endswith(normalized))
    ]
    if len(suffix) == 1:
        return suffix[0]
    if len(suffix) > 1:
        raise ApiAmbiguousError(suffix)

    titled = [e for e in entries if normalized in e.title]
    if len(titled) == 1:
        return titled[0]
    if len(titled) > 1:
        raise ApiAmbiguousError(titled)

    raise ApiNotFoundError(f"未匹配：{normalized}")


def overview_markdown(index_text: str) -> str:
    """overview 工具返回体：内置前言 + 实时索引。"""
    return PREAMBLE + "\n\n" + index_text


# ---------------------------------------------------------------------------
# 索引拉取（进程内 TTL 缓存，降低多工具重复拉取代价）
# ---------------------------------------------------------------------------
_cache: tuple[float, list[DocEntry], str] | None = None


def fetch_index(force: bool = False) -> tuple[list[DocEntry], str]:
    """拉取（或取缓存）llms.txt 索引：返回 (条目列表, 原始文本)。

    Raises:
        http_utils.DownloadError: 拉取失败。
    """
    global _cache
    now = time.monotonic()
    if not force and _cache is not None and _cache[0] > now:
        return _cache[1], _cache[2]
    base = config.doc_base_url()
    text = http_utils.download_content(urljoin(base + "/", "llms.txt"))
    entries = parse_llms_index(text, base)
    ttl = config.index_cache_ttl_seconds()
    _cache = ((now + ttl) if ttl > 0 else now - 1, entries, text)
    return entries, text


def reset_cache() -> None:
    """清空索引缓存（测试用）。"""
    global _cache
    _cache = None
