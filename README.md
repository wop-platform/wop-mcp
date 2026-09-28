# wop-mcp

**万联易达开放平台（WOP）MCP Server —— 让 AI 助手安全、正确地完成 WOP 对接**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![MCP](https://img.shields.io/badge/MCP-Server-orange.svg)](https://modelcontextprotocol.io/)
[![Coverage ≥95%](https://img.shields.io/badge/coverage-%E2%89%A595%25-brightgreen)]()

## 简介

`wop-mcp` 是万联易达开放平台（WOP）的 [Model Context Protocol](https://modelcontextprotocol.io/) Server，
帮助开发者通过 AI 助手（Claude Desktop、Cursor、Claude Code 等）完成 WOP 对接：

- 📚 **文档获取**：接入指南、API 索引、接口详情（自动穿透文档 URL 的时间戳后缀）
- 🔐 **密钥对生成**：RSA2048 / SM2，公钥按分发契约编码返回，可直接上报平台
- 🛡️ **安全纪律**：私钥只写入本地 0600 文件，**永不回显进 AI 对话**（对齐 [wop-skills](https://github.com/wop-platform/wop-skills) SECURITY 纪律）
- 🔌 **即插即用**：stdio transport，`uvx wop-mcp`（PyPI 发布后）一行接入

## 工具总览

| 工具 | 说明 |
|---|---|
| `wop_overview()` | 接入指南（三步流程、securityReq 组合、公钥编码、SDK 列表）+ 实时 `llms.txt` API 索引 |
| `wop_api_detail(api)` | API 详情；入参支持 API 路径（如 `/staffing/open/v1/invoice/apply`，可带 POST 前缀、支持省略业务域前缀的后缀匹配）、接口中文名（如 `转账提交`）、完整 `.md` URL |
| `wop_link_detail(url)` | 文档中心任意子页 / 外链内容（相对路径自动拼接基址，如 `llms-full.txt`） |
| `wop_gen_key_pair(algorithm)` | `RSA2048`（别名 `RSA`）或 `SM2`；返回 `publicKey`（契约编码）+ `privateKeyFile`（0600 路径） |

## 快速开始

### 方式一：uvx 直接运行（PyPI 发布后）

```bash
uvx wop-mcp
```

### 方式二：源码运行

```bash
git clone https://github.com/wop-platform/wop-mcp.git
cd wop-mcp
uv sync
uv run wop-mcp
```

## 在 AI 工具中配置

### Cursor

```json
{
  "mcpServers": {
    "wop-mcp": {
      "command": "uvx",
      "args": ["wop-mcp"],
      "timeout": 600,
      "autoApprove": ["wop_overview", "wop_api_detail", "wop_link_detail"]
    }
  }
}
```

### Claude Desktop

macOS：`~/Library/Application Support/Claude/claude_desktop_config.json`
Windows：`%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "wop-mcp": {
      "command": "uvx",
      "args": ["wop-mcp"]
    }
  }
}
```

源码方式将 `command`/`args` 替换为：

```json
{
  "command": "uv",
  "args": ["--directory", "/path/to/wop-mcp", "run", "wop-mcp"]
}
```

> `wop_gen_key_pair` 写本地私钥文件，建议保留人工确认（未列入 autoApprove）。

## 环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `WOP_DOC_BASE_URL` | `https://assets.wanlianyida.com/gtsp/platformResource/wop/doc-center` | 文档中心基址 |
| `WOP_KEYS_DIR` | `./keys` | 私钥落盘目录（0600 文件） |
| `WOP_INDEX_CACHE_TTL` | `300` | `llms.txt` 索引进程内缓存秒数（`0` 关闭） |
| `WOP_HTTP_TIMEOUT` | `15` | HTTP 超时秒数 |

## 安全纪律

- **私钥只落盘不回显**：`wop_gen_key_pair` 返回值不含任何私钥材料；私钥以 0600 权限独占创建于 `WOP_KEYS_DIR`。
- **公钥即上报格式**：RSA = X.509 SPKI DER 的 Base64；SM2 = 未压缩点 `04‖X‖Y`（65 字节）的 Base64（[crypto-strategy-spec](https://github.com/wop-platform/wop-specs) §3.4，D10/D12）。
- **契约自检**：每次生成后经 [wop-python-sdk](https://github.com/wop-platform/wop-python-sdk) 官方加载器回读（含 SM2 曲线校验），编码不合约即报错。
- `keys/` 目录已入 `.gitignore`，**严禁**将私钥文件提交入库或粘贴进对话。

## 算法说明（与 spec 的差异）

本工具密钥生成支持 `RSA2048` / `SM2`。`crypto-strategy-spec` v0.4 草案的 securityReq
国际族档位为 RSA3072/RSA4096；平台实际接受的 RSA 档位以商户中心审核为准。
国密族与国际族禁止跨族组合。

## 开发

```bash
uv sync                          # 安装依赖（含 dev 组）
uv run pytest --cov=wop_mcp --cov-fail-under=95   # 测试 + 覆盖率门禁
npm i -g lefthook && lefthook install             # 激活 git 钩子（commitlint + 覆盖率门禁）
```

- 提交信息遵循 [Conventional Commits](https://www.conventionalcommits.org/zh-CN/)（commitlint 校验）
- CI：GitHub Actions，Python 3.10–3.13 矩阵，覆盖率红线 95%

## 许可证

[MIT](LICENSE) © 2026 wop-platform
