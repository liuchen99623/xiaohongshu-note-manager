from __future__ import annotations

import json
from typing import Any

PROMPT_VERSION = "1.0"

SYSTEM_PROMPT = """你是“小红书笔记管家”，负责把真实素材和业务目标整理成可执行的小红书内容包。
原则：
1. 使用自然、口语化的简体中文，先交付可直接拍摄、设计或发布的成品。
2. 不编造品牌数据、客户评价、案例、产品功效或个人经历；缺失信息用【待补充】。
3. 标题具体自然，不做夸张承诺；一页或一个镜头只讲一个重点。
4. 输出必须包含目标读者、内容目标、标题、正文/脚本、行动号召、话题、首评和检查清单。
5. 不提供刷量、骚扰、冒充、绕过平台风控、盗用版权素材或自动点击“发布”的方案。
6. 广告、合作、赠品、医疗、金融和 AI 生成内容应提醒依法依规披露。
7. 只返回严格 JSON，不要 Markdown 代码围栏，不要 JSON 之外的说明。
"""

GRAPHIC_SHAPE = {
    "content_goal": "本篇目标",
    "target_reader": "目标读者",
    "title_options": ["3到5个标题"],
    "cover_copy": "封面文案",
    "pages": [{"page": 1, "heading": "本页标题", "body": "本页正文", "visual": "视觉建议"}],
    "caption": "可直接发布的正文",
    "cta": "自然行动号召",
    "hashtags": ["精简话题"],
    "first_comment": "首评建议",
    "preflight": ["发布前检查项"],
    "disclosures": ["必要披露；没有则空数组"],
}

VIDEO_SHAPE = {
    "content_goal": "视频目标",
    "target_reader": "目标读者",
    "duration_seconds": 45,
    "aspect_ratio": "9:16",
    "hook": "前1到3秒钩子",
    "shots": [{"start": 0, "end": 3, "visual": "画面", "action": "动作", "voiceover": "口播", "subtitle": "字幕"}],
    "b_roll": ["补充镜头"],
    "transitions": ["转场建议"],
    "cover_title": "封面标题",
    "caption": "笔记正文",
    "cta": "自然行动号召",
    "hashtags": ["精简话题"],
    "shooting_list": ["拍摄清单"],
    "editing_checklist": ["剪辑检查项"],
    "first_comment": "首评建议",
    "disclosures": ["必要披露；没有则空数组"],
}


def build_prompt(profile: dict[str, Any], brief: dict[str, Any]) -> str:
    shape = GRAPHIC_SHAPE if brief["content_type"] == "graphic" else VIDEO_SHAPE
    return """请根据下面资料制作一个完整内容包。凡资料中没有的事实，不得自行补造，改用【待补充】。

账号档案：
%s

本次简报：
%s

请严格按下面 JSON 结构输出，字段不可缺失：
%s""" % (
        json.dumps(profile, ensure_ascii=False, indent=2),
        json.dumps(brief, ensure_ascii=False, indent=2),
        json.dumps(shape, ensure_ascii=False, indent=2),
    )
