# 小红书笔记管家（Xiaohongshu Note Manager）

[![CI](https://github.com/liuchen99623/xiaohongshu-note-manager/actions/workflows/ci.yml/badge.svg)](https://github.com/liuchen99623/xiaohongshu-note-manager/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

一个**开源、本地优先、可真正运行**的小红书内容工作流助手：从账号定位、内容简报、图文/短视频内容包，到排期与数据复盘，完整走通一条内容生产链路。

> 非官方项目：本项目与小红书、Hermes Agent、Nous Research 或任何模型服务商没有隶属或背书关系。

## 能做什么

- 多账号档案：定位、读者、调性、目标、禁用表达、素材能力；
- 内容简报：主题、目标、图文/短视频、真实素材和限制；
- 图文内容包：标题、封面、逐页文案、视觉建议、正文、CTA、话题、首评、检查清单；
- 短视频内容包：钩子、时长、画幅、分镜、B-roll、转场、字幕、拍摄/剪辑清单；
- 内容排期：只记录计划，不自动发布；
- 数据复盘：录入真实曝光、阅读、互动、收藏、分享、涨粉、主页访问和转化；
- Markdown / JSON 导出；
- OpenAI Chat Completions 兼容接口，不绑定单一模型厂商；
- 附带可用于 Hermes Profile 的通用系统提示词。

## 安全边界

本项目**不会**登录小红书、读取后台、批量回复或自动点击“发布”。发布前必须由用户核验事实、素材授权、必要披露并确认最终版本。项目不提供刷量、骚扰、冒充、盗用素材或规避平台风控的功能。

模型生成结果可能不准确，也不能替代法律、医疗、金融或平台合规审核；MIT 许可证只覆盖本项目自身代码和文档，不自动保证第三方素材或每份模型输出不存在权利风险。

## 快速开始

要求 Python 3.11+，运行时代码只使用标准库。

```bash
git clone https://github.com/liuchen99623/xiaohongshu-note-manager.git
cd xiaohongshu-note-manager

# 推荐：使用 uv
uv tool install .

# 或在虚拟环境内安装
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
```

配置模型（密钥不要提交到 Git）：

```bash
cp .env.example .env
# 手动把 .env 的值导入你的 shell，或直接 export：
export OPENAI_API_KEY='你的密钥'
export OPENAI_BASE_URL='https://api.openai.com/v1'
export OPENAI_MODEL='gpt-4.1-mini'
```

初始化并检查：

```bash
xhs-note-manager init
xhs-note-manager doctor
```

## 5 分钟跑通完整流程

### 1. 建立账号档案

```bash
xhs-note-manager profile add \
  --name "通勤健康餐" \
  --positioning "给上班族的低门槛健康便当" \
  --audience "22—35岁、工作日没时间做饭的人" \
  --tone "真实、清爽、不说教" \
  --goals "涨粉,收藏" \
  --banned "躺瘦,保证减重" \
  --assets "手机实拍,食材特写,步骤照片"
```

### 2. 创建内容简报

```bash
xhs-note-manager brief add \
  --profile 1 \
  --topic "周日晚30分钟备好3天午餐" \
  --objective "涨粉" \
  --type graphic \
  --materials "真实食材：鸡胸、鸡蛋、西兰花；现有6张步骤照片" \
  --constraints "不写减肥功效；预算价格使用【待补充】"
```

`--type` 可选 `graphic` 或 `video`。

### 3. 生成前预览提示词

```bash
xhs-note-manager prompt --brief 1
```

此命令不会调用模型，适合先确认将发送的账号信息和素材。

### 4. 生成内容包

```bash
xhs-note-manager generate --brief 1
xhs-note-manager package show 1
xhs-note-manager export --package 1 --format md --output exports/note-1.md
```

导出默认不覆盖已有文件；确认覆盖时添加 `--force`。

### 5. 加入排期（不自动发布）

```bash
xhs-note-manager calendar add \
  --profile 1 --package 1 \
  --at '2026-11-15T20:00:00+08:00' \
  --notes '发布前确认图片授权和价格'

xhs-note-manager calendar list --profile 1
```

### 6. 发布后录入真实数据

```bash
xhs-note-manager review add \
  --package 1 \
  --impressions 8200 --reads 3100 --likes 268 \
  --comments 31 --saves 489 --shares 42 --follows 76 \
  --profile-visits 210 --conversions 8 \
  --lessons "收藏明显高于点赞，下次继续做可保存的清单"

xhs-note-manager review summary --profile 1
```

指标按平台后台的**当前累计值**录入；同一内容包再次执行 `review add` 会更新该内容包的快照，不会把两次累计值重复相加。汇总会同时给出阅读率、互动率、收藏率、涨粉率和转化率（有可用分母时）。

## 数据与隐私

默认数据库位于操作系统的当前用户数据目录：macOS 为 `~/Library/Application Support/xiaohongshu-note-manager/manager.db`，Linux 通常为 `~/.local/share/xiaohongshu-note-manager/manager.db`，Windows 使用 `%APPDATA%`。可通过 `XHS_MANAGER_DB` 或全局 `--db` 修改。

只有执行 `generate` 时，对应账号档案和简报才会发给你配置的模型服务。远程端点必须使用 HTTPS；无密钥 HTTP 仅允许本机 `localhost` 模型服务。项目不内置遥测，也不会保存 API Key。详见 [PRIVACY.md](https://github.com/liuchen99623/xiaohongshu-note-manager/blob/main/PRIVACY.md)。

## 命令总览

```text
init
doctor
profile add|list|show
brief add|list|show
prompt
generate
package list|show
export
calendar add|list
review add|summary
```

运行 `xhs-note-manager <命令> --help` 查看参数。

## 在 Hermes Agent 中使用

通用身份提示词位于 [`prompts/agent-system.md`](https://github.com/liuchen99623/xiaohongshu-note-manager/blob/main/prompts/agent-system.md)，接入说明见 [`docs/hermes.md`](https://github.com/liuchen99623/xiaohongshu-note-manager/blob/main/docs/hermes.md)。Hermes 的安装和配置以官方文档 <https://hermes-agent.nousresearch.com/docs> 为准。本仓库不会复制任何真实 Hermes Profile 或个人配置。

## 开发与测试

```bash
python3 -m unittest discover -s tests -v
python3 scripts/secret_scan.py .
```

工作流细节见 [docs/workflow.md](https://github.com/liuchen99623/xiaohongshu-note-manager/blob/main/docs/workflow.md)，贡献方式见 [CONTRIBUTING.md](https://github.com/liuchen99623/xiaohongshu-note-manager/blob/main/CONTRIBUTING.md)，版本变化见 [CHANGELOG.md](https://github.com/liuchen99623/xiaohongshu-note-manager/blob/main/CHANGELOG.md)，社区约定见 [CODE_OF_CONDUCT.md](https://github.com/liuchen99623/xiaohongshu-note-manager/blob/main/CODE_OF_CONDUCT.md)。

## License

[MIT](https://github.com/liuchen99623/xiaohongshu-note-manager/blob/main/LICENSE)
