# -*- coding: utf-8 -*-
"""wop-mcp Server 入口：4 个 MCP 工具（stdio transport）。

- wop_overview()                接入指南前言 + 实时 llms.txt 索引
- wop_api_detail(api)           API 路径 / 中文名 / 完整 .md URL → 接口详情
- wop_link_detail(url)          文档中心任意子页 / 外链内容
- wop_gen_key_pair(algorithm)   RSA2048 / SM2 密钥对（私钥只落盘不回显）
"""
from __future__ import annotations

from typing import Any, Dict

from mcp.server import MCPServer

from . import __version__, config, http_utils
from .doc_center import (
    ApiAmbiguousError,
    ApiNotFoundError,
    DocEntry,
    fetch_index,
    overview_markdown,
    resolve_api,
)
from .keypair import gen_key_pair

mcp = MCPServer("wop-mcp", version=__version__)


def _format_entries(entries: list[DocEntry]) -> str:
    return "\n".join(
        f"- {entry.title}：`{entry.method} {entry.api_path}`" for entry in entries
    )


@mcp.tool()
def wop_overview() -> str:
    """获取万联易达开放平台（WOP）的接入指南与全部 API 索引。

    内容包含：三步接入流程、securityReq 算法组合、公钥分发编码、官方 SDK 与
    工具列表，以及实时拉取的 llms.txt API 索引（按业务域分组）。
    索引中的 API 可用 wop_api_detail 进一步获取详情，链接可用 wop_link_detail 获取。

    Returns:
        str: 接入指南 + API 索引（markdown 格式）
    """
    try:
        _, index_text = fetch_index()
    except http_utils.DownloadError as exc:
        return str(exc)
    return overview_markdown(index_text)


@mcp.tool()
def wop_api_detail(api: str) -> str:
    """获取万联易达开放平台（WOP）指定 API 接口的详细定义。

    支持三种入参形态（按优先级）：
    1. API 路径：如 /staffing/open/v1/invoice/apply（可带 POST/GET 前缀，
       支持省略业务域前缀的后缀匹配）
    2. 接口中文名：如 转账提交
    3. 完整 .md URL：直通下载

    匹配到多个接口时返回候选列表，请用更精确的路径或 URL 重试。

    Args:
        api: str - API 路径、接口中文名或完整 .md URL

    Returns:
        str: API 接口详情（markdown 格式：基本信息、请求参数、响应参数、示例等）
    """
    query = (api or "").strip()
    if not query:
        return (
            "api 参数为空：请传入 API 路径（如 /staffing/open/v1/invoice/apply）、"
            "接口中文名（如 转账提交）或完整 .md URL"
        )
    if query.startswith("http://") or query.startswith("https://"):
        try:
            return http_utils.download_content(query)
        except http_utils.DownloadError as exc:
            return str(exc)
    try:
        entries, _ = fetch_index()
    except http_utils.DownloadError as exc:
        return str(exc)
    try:
        entry = resolve_api(query, entries)
    except ApiAmbiguousError as exc:
        return (
            "匹配到多个接口，请用完整路径或完整 .md URL 精确指定：\n"
            + _format_entries(exc.candidates)
        )
    except ApiNotFoundError:
        return "未匹配到接口。当前索引全部接口：\n" + _format_entries(entries)
    try:
        return http_utils.download_content(entry.url)
    except http_utils.DownloadError as exc:
        return str(exc)


@mcp.tool()
def wop_link_detail(url: str) -> str:
    """获取万联易达开放平台（WOP）文档中心子页面或外部链接的详细内容。

    接受完整 URL，或文档中心相对路径（自动拼接文档中心基址，
    如 staffing/api/staffing/open/v1/invoice/apply.2026….md 或 llms-full.txt）。

    Args:
        url: str - 完整 URL 或文档中心相对路径

    Returns:
        str: 页面内容（markdown 格式）
    """
    target = (url or "").strip()
    if not target:
        return "url 参数为空：请传入完整 URL 或文档中心相对路径"
    if not (target.startswith("http://") or target.startswith("https://")):
        target = config.doc_base_url() + "/" + target.lstrip("/")
    try:
        return http_utils.download_content(target)
    except http_utils.DownloadError as exc:
        return str(exc)


@mcp.tool()
def wop_gen_key_pair(algorithm: str = "RSA2048") -> Dict[str, Any]:
    """生成 WOP 对接所需的非对称密钥对（RSA2048 / SM2）。

    安全纪律：私钥只写入本地 0600 文件，不会出现在返回值或对话中；
    返回的 publicKey 为分发契约编码（RSA：SPKI DER Base64；
    SM2：未压缩点 04‖X‖Y Base64），可直接上报平台。

    Args:
        algorithm: str - "RSA2048"（别名 "RSA"）或 "SM2"，默认 "RSA2048"

    Returns:
        Dict 包含 algorithm / publicKey / privateKeyFile(路径) / message
    """
    return gen_key_pair(algorithm)


def main() -> None:
    """Server 入口：stdio transport。"""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
