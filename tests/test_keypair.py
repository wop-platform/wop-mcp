# -*- coding: utf-8 -*-
"""keypair 单元测试：契约编码、私钥纪律（0600 落盘、不回显）、确定性推导、算法校验。"""
import base64
import json
import os
import stat

import pytest
from cryptography.hazmat.primitives import serialization
from wop_sdk.keys import (
    load_rsa_public_key,
    load_sm2_private_key,
    load_sm2_public_key,
)
from wop_sdk.sm2crypto import sm2_derive_public_hex

from wop_mcp import keypair


def _mode(path) -> int:
    return stat.S_IMODE(os.stat(path).st_mode)


def test_gen_rsa2048_contract_and_discipline(tmp_path):
    result = keypair.gen_key_pair("RSA2048", keys_dir=tmp_path)
    assert set(result.keys()) == set(keypair.RESULT_KEYS)
    assert result["algorithm"] == "RSA2048"

    # 公钥：SPKI DER Base64，官方加载器可回读（expected_bits=2048）
    public = load_rsa_public_key(result["publicKey"], expected_bits=2048)
    assert public.key_size == 2048

    # 私钥文件：0600、PKCS8 PEM、可被 cryptography 解析
    private_path = result["privateKeyFile"]
    assert private_path.startswith(str(tmp_path))
    assert _mode(private_path) == 0o600
    with open(private_path, encoding="ascii") as handle:
        pem_text = handle.read()
    assert "-----BEGIN PRIVATE KEY-----" in pem_text
    serialization.load_pem_private_key(pem_text.encode(), password=None)

    # 私钥纪律：返回值中不含任何私钥材料
    dumped = json.dumps(result, ensure_ascii=False)
    assert "BEGIN PRIVATE KEY" not in dumped
    assert result["message"]


def test_gen_rsa_alias_normalization(tmp_path):
    result = keypair.gen_key_pair(" rsa ", keys_dir=tmp_path)
    assert result["algorithm"] == "RSA2048"


def test_gen_sm2_contract_and_discipline(tmp_path):
    result = keypair.gen_key_pair("SM2", keys_dir=tmp_path)
    assert result["algorithm"] == "SM2"

    # 公钥：65 字节未压缩点 04‖X‖Y 的 Base64，官方加载器（含曲线校验）可回读
    uncompressed = base64.b64decode(result["publicKey"])
    assert len(uncompressed) == 65
    assert uncompressed[0] == 0x04
    load_sm2_public_key(result["publicKey"])

    # 私钥文件：0600、Base64(32 字节标量 d)、范围 [1, n)
    private_path = result["privateKeyFile"]
    assert _mode(private_path) == 0o600
    with open(private_path, encoding="ascii") as handle:
        material = handle.read().strip()
    d_bytes = load_sm2_private_key(material)
    assert len(d_bytes) == 32

    # 私钥纪律：Base64 私钥材料不出现在返回值中
    assert material not in json.dumps(result)


def test_gen_sm2_deterministic_derivation(tmp_path):
    fixed_d = bytes(31) + b"\x01"
    result = keypair.gen_key_pair("SM2", keys_dir=tmp_path, sm2_d_bytes=fixed_d)
    expected = base64.b64encode(
        b"\x04" + bytes.fromhex(sm2_derive_public_hex(fixed_d.hex()))
    ).decode("ascii")
    assert result["publicKey"] == expected


def test_gen_unsupported_algorithm_raises(tmp_path):
    with pytest.raises(ValueError, match="RSA3072"):
        keypair.gen_key_pair("RSA3072", keys_dir=tmp_path)
    with pytest.raises(ValueError):
        keypair.gen_key_pair("", keys_dir=tmp_path)


def test_generate_sm2_rejects_bad_scalar_length():
    with pytest.raises(ValueError, match="32 字节"):
        keypair._generate_sm2(d_bytes=b"\x01" * 31)


def test_write_private_file_never_overwrites(tmp_path):
    content = "secret-material"
    first = keypair._write_private_file(tmp_path, "sm2", ".key", content)
    second = keypair._write_private_file(tmp_path, "sm2", ".key", content)
    assert first != second
    assert _mode(first) == 0o600
    assert _mode(second) == 0o600


def test_keys_dir_default_from_env(monkeypatch, tmp_path):
    monkeypatch.setenv("WOP_KEYS_DIR", str(tmp_path / "custom"))
    result = keypair.gen_key_pair("SM2")
    assert result["privateKeyFile"].startswith(str(tmp_path / "custom"))
