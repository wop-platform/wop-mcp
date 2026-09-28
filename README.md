# WOP MCP

万联易达开放平台（WOP）的 [MCP](https://modelcontextprotocol.io)（Model Context Protocol）服务器：将 WOP 能力以 tools / resources 形式暴露给 AI 编码助手与智能体。

## 状态

空仓起步（2026-09-28 初始化）。能力面与技术栈均未定型，下表为候选方向，立项前以本 README 为讨论基准。

## 候选能力面（待评审）

| 方向 | 说明 | 对齐规格 |
|------|------|----------|
| 文档检索 | wop-specs 规格文档的问答/检索 tools | [wop-specs](https://github.com/wop-platform/wop-specs) |
| 报文工具 | canonicalRequest 构造、验签、加解密调试 | crypto-strategy-spec |
| API 调用 | 基于官方 SDK 的出向调用编排（header 契约、WopError 闭集） | wop-sdk-spec §2.1 / §2.2 |

## 相关仓库

- [wop-specs](https://github.com/wop-platform/wop-specs) — 协议契约与跨语言测试向量唯一真源
- [wop-web-tools](https://github.com/wop-platform/wop-web-tools) — 浏览器端人工工作台（面向商户）
- 六语言官方 SDK（wop-java-sdk / wop-go-sdk / wop-php-sdk / wop-python-sdk / wop-dotnet-sdk / wop-typescript-sdk）
