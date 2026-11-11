# 在 Hermes Agent 中使用

本仓库不包含任何个人 Profile、聊天记录、密钥或平台 Cookie。推荐把 `prompts/agent-system.md` 的内容复制到一个独立 Hermes Profile 的身份/指令文件中，再把 CLI 当作本地工作流工具调用。

官方 Hermes 文档以 <https://hermes-agent.nousresearch.com/docs> 为准。不同版本的 Profile 与 Gateway 命令可能变化，接入前请按当前文档操作。

原则：

- 一个业务角色使用一个独立 Profile；
- 密钥只放本机环境变量或官方密钥存储，不提交到 Git；
- 保留工具审批；
- 发布动作必须人工确认；
- 不复制真实 `~/.hermes` 目录到公开仓库。
