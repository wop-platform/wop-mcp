# -*- coding: utf-8 -*-
"""运行配置：环境变量可覆盖，默认值指向生产文档中心 CDN。

环境变量清单：
- WOP_DOC_BASE_URL       文档中心基址（默认 assets.wanlianyida.com …/doc-center）
- WOP_KEYS_DIR           密钥对私钥落盘目录（默认 ./keys）
- WOP_INDEX_CACHE_TTL    llms.txt 索引进程内缓存秒数（默认 300；<=0 表示不缓存）
- WOP_HTTP_TIMEOUT       HTTP 超时秒数（默认 15）
"""
from __future__ import annotations

import os
from pathlib import Path

DEFAULT_DOC_BASE_URL = (
    "https://assets.wanlianyida.com/gtsp/platformResource/wop/doc-center"
)
DEFAULT_KEYS_DIR = "./keys"
DEFAULT_INDEX_CACHE_TTL_SECONDS = 300.0
DEFAULT_HTTP_TIMEOUT_SECONDS = 15.0


def doc_base_url() -> str:
    """文档中心基址（去尾部斜杠）。"""
    return os.environ.get("WOP_DOC_BASE_URL", DEFAULT_DOC_BASE_URL).rstrip("/")


def keys_dir() -> Path:
    """私钥落盘目录。"""
    return Path(os.environ.get("WOP_KEYS_DIR", DEFAULT_KEYS_DIR))


def index_cache_ttl_seconds() -> float:
    """llms.txt 索引缓存 TTL（秒）。"""
    raw = os.environ.get("WOP_INDEX_CACHE_TTL", "")
    try:
        return float(raw)
    except ValueError:
        return DEFAULT_INDEX_CACHE_TTL_SECONDS


def http_timeout_seconds() -> float:
    """HTTP 下载超时（秒）。"""
    raw = os.environ.get("WOP_HTTP_TIMEOUT", "")
    try:
        return float(raw)
    except ValueError:
        return DEFAULT_HTTP_TIMEOUT_SECONDS
