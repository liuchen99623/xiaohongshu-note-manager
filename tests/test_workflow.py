from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from xhs_note_manager.db import Database
from xhs_note_manager.workflow import ContentWorkflow, package_to_markdown, parse_json_object, validate_package


GRAPHIC = {
    "content_goal": "让读者保存备餐清单",
    "target_reader": "忙碌上班族",
    "title_options": ["30分钟备好3天午餐", "上班族备餐清单", "周日这样准备工作餐"],
    "cover_copy": "30分钟备餐",
    "pages": [{"page": 1, "heading": "先看结果", "body": "3份便当", "visual": "俯拍"}],
    "caption": "这是一份可执行的备餐记录。",
    "cta": "你最想先看哪一步？",
    "hashtags": ["上班族便当", "备餐"],
    "first_comment": "价格请按当地实际食材填写。",
    "preflight": ["确认价格", "确认图片授权"],
    "disclosures": [],
}

VIDEO = {
    "content_goal": "让新手拍出可执行的短视频",
    "target_reader": "第一次拍口播的人",
    "duration_seconds": 30,
    "aspect_ratio": "9:16",
    "hook": "手机放这里，画面立刻稳一半",
    "shots": [{"start": 0, "end": 3, "visual": "桌面全景", "action": "放下手机", "voiceover": "先别急着买设备", "subtitle": "先别买设备"}],
    "b_roll": ["手机支架特写"],
    "transitions": ["直接切镜"],
    "cover_title": "新手口播怎么拍",
    "caption": "用手边设备先完成第一条。",
    "cta": "你卡在拍摄还是剪辑？",
    "hashtags": ["短视频拍摄"],
    "shooting_list": ["手机", "窗边自然光"],
    "editing_checklist": ["检查字幕"],
    "first_comment": "设备不是开始的门槛。",
    "disclosures": [],
}


class FakeClient:
    def complete(self, *, system: str, user: str) -> str:
        self.system = system
        self.user = user
        return json.dumps(GRAPHIC, ensure_ascii=False)


class WorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.temp.name) / "manager.db")
        self.db.init()
        self.profile = self.db.add_profile(
            name="测试账号", positioning="实用内容", audience="上班族", tone="自然",
            goals=["收藏"], banned=["保证"], assets=["手机照片"],
        )
        self.brief = self.db.add_brief(
            profile_id=self.profile, topic="30分钟备餐", objective="涨粉",
            content_type="graphic", materials="真实步骤照片", constraints="不写功效",
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_generate_save_and_export(self) -> None:
        client = FakeClient()
        package_id = ContentWorkflow(self.db, client, "fake-model").generate(self.brief)
        package = self.db.get_package(package_id)
        self.assertEqual(package["title"], GRAPHIC["title_options"][0])
        self.assertEqual(package["prompt_version"], "1.0")
        self.assertIn("不写功效", client.user)
        markdown = package_to_markdown(package)
        self.assertIn("## 分页内容", markdown)
        self.assertIn("#上班族便当", markdown)

    def test_calendar_and_review(self) -> None:
        package_id = ContentWorkflow(self.db, FakeClient(), "fake-model").generate(self.brief)
        self.db.add_calendar(profile_id=self.profile, package_id=package_id, publish_at="2026-11-15T20:00:00+08:00")
        self.assertEqual(len(self.db.list_calendar(self.profile)), 1)
        self.db.add_review(package_id=package_id, metrics={"reads": 100, "saves": 20}, lessons="清单有效")
        self.db.add_review(package_id=package_id, metrics={"reads": 120, "saves": 24}, lessons="更新后的累计数据")
        self.assertEqual(
            self.db.review_summary(self.profile),
            {
                "review_count": 1,
                "totals": {"reads": 120, "saves": 24},
                "rates": {
                    "interaction_rate": 0.2,
                    "save_rate": 0.2,
                    "follow_rate": 0.0,
                    "conversion_rate": 0.0,
                },
            },
        )

    def test_json_fence_and_validation(self) -> None:
        self.assertEqual(parse_json_object("```json\n{\"a\": 1}\n```"), {"a": 1})
        validate_package(GRAPHIC, "graphic")
        broken = dict(GRAPHIC)
        broken["title_options"] = ["只有一个"]
        with self.assertRaises(ValueError):
            validate_package(broken, "graphic")

    def test_video_generation_and_export(self) -> None:
        video_brief = self.db.add_brief(
            profile_id=self.profile, topic="新手口播", objective="互动",
            content_type="video", materials="手机和窗边光", constraints="低成本",
        )

        class VideoClient:
            def complete(self, *, system: str, user: str) -> str:
                return json.dumps(VIDEO, ensure_ascii=False)

        package_id = ContentWorkflow(self.db, VideoClient(), "fake-model").generate(video_brief)
        markdown = package_to_markdown(self.db.get_package(package_id))
        self.assertIn("## 分镜表", markdown)
        self.assertIn("新手口播怎么拍", markdown)

    def test_calendar_requires_timezone(self) -> None:
        with self.assertRaises(ValueError):
            self.db.add_calendar(
                profile_id=self.profile,
                package_id=None,
                publish_at="2026-11-15T20:00:00",
            )

    def test_calendar_sorts_by_utc_instant(self) -> None:
        later = self.db.add_calendar(
            profile_id=self.profile,
            package_id=None,
            publish_at="2025-12-31T23:00:00-12:00",
        )
        earlier = self.db.add_calendar(
            profile_id=self.profile,
            package_id=None,
            publish_at="2026-01-01T00:30:00+14:00",
        )
        self.assertEqual([row["id"] for row in self.db.list_calendar(self.profile)], [earlier, later])

    def test_malformed_nested_output_is_not_persisted(self) -> None:
        broken = dict(GRAPHIC)
        broken["pages"] = [1]

        class BrokenClient:
            def complete(self, *, system: str, user: str) -> str:
                return json.dumps(broken, ensure_ascii=False)

        with self.assertRaisesRegex(ValueError, "必须是 JSON 对象"):
            ContentWorkflow(self.db, BrokenClient(), "fake-model").generate(self.brief)
        self.assertEqual(self.db.list_packages(self.profile), [])

        bad_video = dict(VIDEO)
        bad_video["shots"] = [{"start": 2, "end": 1}]
        with self.assertRaises(ValueError):
            validate_package(bad_video, "video")
        with self.assertRaisesRegex(ValueError, "不支持"):
            validate_package({}, "unknown")


if __name__ == "__main__":
    unittest.main()
