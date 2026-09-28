# -*- coding: utf-8 -*-
"""密钥对生成：RSA2048 / SM2。

安全纪律（对齐 wop-skills SECURITY.md / wop-cli keygen 行为）：
- 私钥**只**写入本地 0600 文件（O_EXCL 创建），永不进入返回值 / MCP 响应 / 会话日志；
- publicKey 按分发契约编码返回，可直接上报平台。

密码学复用 wop-python-sdk（PyPI 已发布），继承其契约校验：
- RSA 公钥 = X.509 SubjectPublicKeyInfo DER → Base64（spec §3.4）
- SM2 公钥 = 未压缩点 04‖X‖Y（65 字节）→ Base64；私钥 = 32 字节大端标量 d → Base64
- 生成后经 wop_sdk 加载器回读自检（含 SM2 曲线归属 I5 校验），
  同时固化对 gmssl ``_kg`` 内部方法（sm2_derive_public_hex）的脆弱耦合回归。
"""
from __future__ import annotations

import base64
import os
import secrets
import time
from pathlib import Path
from typing import Any, Dict, Optional

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa as _rsa
from gmssl.sm2 import default_ecc_table
from wop_sdk.keys import (
    load_rsa_public_key,
    load_sm2_private_key,
    load_sm2_public_key,
)
from wop_sdk.sm2crypto import sm2_derive_public_hex

from . import config

_SM2_N = int(default_ecc_table["n"], 16)
RSA_BITS = 2048

RESULT_KEYS = ("algorithm", "publicKey", "privateKeyFile", "message")


def _write_private_file(directory: Path, stem: str, suffix: str, content: str) -> Path:
    """将私钥内容写入 0600 新文件（O_EXCL 防覆盖），返回路径。"""
    if not directory.exists():
        directory.mkdir(parents=True, mode=0o700, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    while True:
        path = directory / f"{stem}_{timestamp}_{secrets.token_hex(4)}{suffix}"
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            continue
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        return path


def _generate_rsa2048() -> tuple[str, str]:
    """生成 RSA2048 密钥对：返回 (公钥 Base64, 私钥 PKCS8 PEM)。"""
    private_key = _rsa.generate_private_key(public_exponent=65537, key_size=RSA_BITS)
    spki_der = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    public_b64 = base64.b64encode(spki_der).decode("ascii")
    # 契约自检：分发编码必须能被官方加载器回读（§3.4）
    load_rsa_public_key(public_b64, expected_bits=RSA_BITS)
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")
    return public_b64, pem


def _generate_sm2(d_bytes: Optional[bytes] = None) -> tuple[str, str]:
    """生成 SM2 密钥对：返回 (公钥 Base64, 私钥 Base64)。

    d_bytes 仅供确定性测试注入；生产路径由 CSPRNG 采样 d ∈ [1, n)。
    """
    if d_bytes is None:
        scalar = secrets.randbelow(_SM2_N - 1) + 1
        d_bytes = scalar.to_bytes(32, "big")
    if len(d_bytes) != 32:
        raise ValueError("SM2 私钥标量必须为 32 字节")
    private_b64 = base64.b64encode(d_bytes).decode("ascii")
    xy_hex = sm2_derive_public_hex(d_bytes.hex())
    uncompressed = b"\x04" + bytes.fromhex(xy_hex)
    public_b64 = base64.b64encode(uncompressed).decode("ascii")
    # 契约自检：曲线归属（I5）+ 标量范围 + 私钥材料编码
    load_sm2_public_key(public_b64)
    if load_sm2_private_key(private_b64) != d_bytes:
        raise RuntimeError("SM2 私钥材料契约自检失败")
    return public_b64, private_b64


def gen_key_pair(
    algorithm: str = "RSA2048",
    keys_dir: Optional[Path] = None,
    sm2_d_bytes: Optional[bytes] = None,
) -> Dict[str, Any]:
    """生成密钥对；私钥只落盘不回显。

    Args:
        algorithm: "RSA2048"（别名 "RSA"）或 "SM2"。
        keys_dir: 私钥目录（默认取 WOP_KEYS_DIR 或 ./keys）；仅测试注入。
        sm2_d_bytes: 仅测试注入的 SM2 确定性标量。

    Returns:
        {"algorithm", "publicKey"(分发契约编码), "privateKeyFile"(0600 文件路径), "message"}
    """
    normalized = (algorithm or "").strip().upper()
    if normalized == "RSA":
        normalized = "RSA2048"
    if normalized not in ("RSA2048", "SM2"):
        raise ValueError(f"不支持的算法 {algorithm!r}；可选：RSA2048 / SM2")

    directory = Path(keys_dir) if keys_dir is not None else config.keys_dir()

    if normalized == "RSA2048":
        public_b64, private_material = _generate_rsa2048()
        path = _write_private_file(directory, "rsa2048", ".pem", private_material)
    else:
        public_b64, private_material = _generate_sm2(sm2_d_bytes)
        path = _write_private_file(directory, "sm2", ".key", private_material)

    return {
        "algorithm": normalized,
        "publicKey": public_b64,
        "privateKeyFile": str(path.resolve()),
        "message": (
            "私钥已写入 0600 本地文件且未在响应中回显；"
            "publicKey 为分发契约编码，可直接上报平台。请妥善保管私钥文件。"
        ),
    }
