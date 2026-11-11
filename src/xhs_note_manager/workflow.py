from __future__ import annotations

import json
from typing import Any, Protocol

from .db import Database
from .prompts import PROMPT_VERSION, SYSTEM_PROMPT, build_prompt


class Completer(Protocol):
    def complete(self, *, system: str, user: str) -> str: ...


REQUIRED = {
    "graphic": {"content_goal", "target_reader", "title_options", "cover_copy", "pages", "caption", "cta", "hashtags", "first_comment", "preflight", "disclosures"},
    "video": {"content_goal", "target_reader", "duration_seconds", "aspect_ratio", "hook", "shots", "b_roll", "transitions", "cover_title", "caption", "cta", "hashtags", "shooting_list", "editing_checklist", "first_comment", "disclosures"},
}


def parse_json_object(text: str) -> dict[str, Any]:
    value = text.strip()
    if value.startswith("```"):
        lines = value.splitlines()
        value = "\n".join(lines[1:-1]).strip()
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"模型输出不是有效 JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("模型输出必须是 JSON 对象")
    return parsed


def _require_text(payload: dict[str, Any], field: str) -> None:
    value = payload[field]
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"模型输出字段 {field} 必须是非空文本")


def _require_text_list(payload: dict[str, Any], field: str, *, allow_empty: bool = True) -> None:
    value = payload[field]
    if not isinstance(value, list) or (not allow_empty and not value):
        raise ValueError(f"模型输出字段 {field} 必须是文本数组")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError(f"模型输出字段 {field} 只能包含非空文本")


def validate_package(payload: dict[str, Any], content_type: str) -> None:
    if content_type not in REQUIRED:
        raise ValueError(f"不支持的内容类型: {content_type}")
    missing = sorted(REQUIRED[content_type] - payload.keys())
    if missing:
        raise ValueError("模型输出缺少字段: " + ", ".join(missing))

    for field in ("content_goal", "target_reader", "caption", "cta", "first_comment"):
        _require_text(payload, field)
    for field in ("hashtags", "disclosures"):
        _require_text_list(payload, field)

    if content_type == "graphic":
        _require_text(payload, "cover_copy")
        _require_text_list(payload, "title_options", allow_empty=False)
        _require_text_list(payload, "preflight", allow_empty=False)
        if not 3 <= len(payload["title_options"]) <= 5:
            raise ValueError("图文标题备选必须为 3 到 5 个")
        pages = payload["pages"]
        if not isinstance(pages, list) or not pages:
            raise ValueError("图文内容至少需要 1 页")
        for index, page in enumerate(pages, start=1):
            if not isinstance(page, dict):
                raise ValueError(f"第 {index} 页必须是 JSON 对象")
            if set(("page", "heading", "body", "visual")) - page.keys():
                raise ValueError(f"第 {index} 页缺少 page/heading/body/visual 字段")
            if isinstance(page["page"], bool) or not isinstance(page["page"], int) or page["page"] < 1:
                raise ValueError(f"第 {index} 页的 page 必须是正整数")
            for field in ("heading", "body", "visual"):
                if not isinstance(page[field], str) or not page[field].strip():
                    raise ValueError(f"第 {index} 页的 {field} 必须是非空文本")
        return

    for field in ("aspect_ratio", "hook", "cover_title"):
        _require_text(payload, field)
    for field in ("b_roll", "transitions", "shooting_list", "editing_checklist"):
        _require_text_list(payload, field)
    duration = payload["duration_seconds"]
    if isinstance(duration, bool) or not isinstance(duration, int) or not 1 <= duration <= 600:
        raise ValueError("duration_seconds 必须是 1 到 600 的整数")
    shots = payload["shots"]
    if not isinstance(shots, list) or not shots:
        raise ValueError("短视频至少需要 1 个分镜")
    for index, shot in enumerate(shots, start=1):
        if not isinstance(shot, dict):
            raise ValueError(f"第 {index} 个分镜必须是 JSON 对象")
        if set(("start", "end", "visual", "action", "voiceover", "subtitle")) - shot.keys():
            raise ValueError(f"第 {index} 个分镜字段不完整")
        start, end = shot["start"], shot["end"]
        numeric = (int, float)
        if isinstance(start, bool) or isinstance(end, bool) or not isinstance(start, numeric) or not isinstance(end, numeric):
            raise ValueError(f"第 {index} 个分镜的 start/end 必须是数字")
        if start < 0 or end <= start:
            raise ValueError(f"第 {index} 个分镜的时间范围无效")
        for field in ("visual", "action", "voiceover", "subtitle"):
            if not isinstance(shot[field], str) or not shot[field].strip():
                raise ValueError(f"第 {index} 个分镜的 {field} 必须是非空文本")


class ContentWorkflow:
    def __init__(self, db: Database, client: Completer, model: str):
        self.db = db
        self.client = client
        self.model = model

    def prompt_for(self, brief_id: int) -> str:
        brief = self.db.get_brief(brief_id)
        profile = self.db.get_profile(int(brief["profile_id"]))
        return build_prompt(profile, brief)

    def generate(self, brief_id: int) -> int:
        brief = self.db.get_brief(brief_id)
        prompt = self.prompt_for(brief_id)
        raw = self.client.complete(system=SYSTEM_PROMPT, user=prompt)
        payload = parse_json_object(raw)
        validate_package(payload, brief["content_type"])
        title = (payload.get("title_options") or [payload.get("cover_title")])[0]
        return self.db.add_package(
            brief_id=brief_id,
            content_type=brief["content_type"],
            title=str(title),
            payload=payload,
            model=self.model,
            prompt_version=PROMPT_VERSION,
        )


def package_to_markdown(package: dict[str, Any]) -> str:
    p = package["payload"]
    lines = [f"# {package['title']}", "", f"> 内容包 ID：{package['id']} · 类型：{package['content_type']} · 模型：{package['model']} · 提示词：{package['prompt_version']}", ""]
    if package["content_type"] == "graphic":
        lines += ["## 内容目标", p["content_goal"], "", "## 目标读者", p["target_reader"], "", "## 标题备选"]
        lines += [f"- {x}" for x in p["title_options"]]
        lines += ["", "## 封面文案", p["cover_copy"], "", "## 分页内容"]
        for page in p["pages"]:
            lines += [f"### 第 {page.get('page', '')} 页 · {page.get('heading', '')}", page.get("body", ""), "", f"**视觉建议：** {page.get('visual', '')}", ""]
        lines += ["## 可直接发布的正文", p["caption"], "", "## 行动号召", p["cta"], "", "## 首评", p["first_comment"], "", "## 发布前检查"]
        lines += [f"- [ ] {x}" for x in p["preflight"]]
    else:
        lines += ["## 视频目标", p["content_goal"], "", "## 目标读者", p["target_reader"], "", f"**建议时长：** {p['duration_seconds']} 秒  ", f"**画幅：** {p['aspect_ratio']}", "", "## 前 1—3 秒钩子", p["hook"], "", "## 分镜表", "", "| 时间 | 画面 | 动作 | 口播/旁白 | 屏幕字幕 |", "|---|---|---|---|---|"]
        for shot in p["shots"]:
            lines.append(f"| {shot.get('start','')}-{shot.get('end','')}s | {shot.get('visual','')} | {shot.get('action','')} | {shot.get('voiceover','')} | {shot.get('subtitle','')} |")
        lines += ["", "## B-roll", *[f"- {x}" for x in p["b_roll"]], "", "## 转场", *[f"- {x}" for x in p["transitions"]], "", "## 封面标题", p["cover_title"], "", "## 笔记正文", p["caption"], "", "## 行动号召", p["cta"], "", "## 首评", p["first_comment"], "", "## 拍摄清单", *[f"- [ ] {x}" for x in p["shooting_list"]], "", "## 剪辑检查", *[f"- [ ] {x}" for x in p["editing_checklist"]]]
    lines += ["", "## 话题", " ".join(f"#{x.lstrip('#')}" for x in p["hashtags"])]
    if p.get("disclosures"):
        lines += ["", "## 合规披露", *[f"- {x}" for x in p["disclosures"]]]
    return "\n".join(str(x) for x in lines).rstrip() + "\n"
