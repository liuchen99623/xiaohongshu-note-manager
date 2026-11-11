# Changelog

本项目遵循语义化版本，重要变化记录在此文件。

## [0.1.0] - 2026-11-11

### Added

- 多账号定位与受众档案；
- 图文、短视频内容简报与结构化生成；
- OpenAI Chat Completions 兼容客户端；
- 本地 SQLite 持久化、排期和真实数据复盘；
- Markdown/JSON 安全导出；
- 中文快速开始、Hermes 通用提示词、隐私与安全文档；
- Python 3.11—3.13 GitHub Actions 测试与密钥扫描。

### Security

- 不保存 API Key；远程端点强制 HTTPS；
- 禁止自动发布、私有接口和绕过平台风控；
- 数据库及导出文件默认使用仅当前用户读写的文件权限。
