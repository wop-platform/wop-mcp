# -*- coding: utf-8 -*-
"""HTTP 下载工具：stdlib urllib 实现，零额外依赖；失败重试一次后抛 DownloadError。"""
from __future__ import annotations

import urllib.error
import urllib.request

from . import __version__, config

RETRIES = 1


class DownloadError(RuntimeError):
    """下载失败（含 URL 与原因，供 MCP 工具直接以字符串外显）。"""


def download_content(url: str, timeout: float | None = None) -> str:
    """GET 下载文本内容（UTF-8）。

    Args:
        url: 完整 URL。
        timeout: 单次尝试超时秒数。

    Returns:
        响应正文文本。

    Raises:
        DownloadError: 重试耗尽仍失败。
    """
    if timeout is None:
        timeout = config.http_timeout_seconds()
    last_error: Exception | None = None
    for _ in range(RETRIES + 1):
        try:
            request = urllib.request.Request(
                url, headers={"User-Agent": f"wop-mcp/{__version__}"}
            )
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read().decode("utf-8", errors="replace")
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
    raise DownloadError(f"HTTP 请求失败 url={url} 原因={last_error}") from last_error
