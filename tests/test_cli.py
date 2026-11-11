from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from xhs_note_manager.cli import main
from xhs_note_manager.db import Database


class CliTests(unittest.TestCase):
    def test_local_lifecycle_without_api_call(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "cli.db")
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(main(["--db", db, "init"]), 0)
                self.assertEqual(main(["--db", db, "profile", "add", "--name", "账号", "--positioning", "定位", "--audience", "读者"]), 0)
                self.assertEqual(main(["--db", db, "brief", "add", "--profile", "1", "--topic", "选题", "--objective", "互动", "--type", "graphic"]), 0)
                self.assertEqual(main(["--db", db, "prompt", "--brief", "1"]), 0)
            value = out.getvalue()
            self.assertIn("数据库已初始化", value)
            self.assertIn("内容简报已创建：1", value)
            self.assertIn("选题", value)

            database = Database(db)
            package_id = database.add_package(
                brief_id=1,
                content_type="graphic",
                title="测试导出",
                payload={},
                model="fake-model",
                prompt_version="1.0",
            )
            output = str(Path(tmp) / "package.json")
            errors = io.StringIO()
            with redirect_stdout(out), redirect_stderr(errors):
                self.assertEqual(main(["--db", db, "export", "--package", str(package_id), "--format", "json", "--output", output]), 0)
                self.assertEqual(main(["--db", db, "export", "--package", str(package_id), "--format", "json", "--output", output]), 2)
                self.assertEqual(main(["--db", db, "export", "--package", str(package_id), "--format", "json", "--output", output, "--force"]), 0)
            self.assertIn("--force", errors.getvalue())

            target = Path(tmp) / "target.txt"
            target.write_text("do not replace", encoding="utf-8")
            link = Path(tmp) / "link.json"
            link.symlink_to(target)
            with redirect_stderr(errors):
                self.assertEqual(main(["--db", db, "export", "--package", str(package_id), "--format", "json", "--output", str(link), "--force"]), 2)
            self.assertEqual(target.read_text(encoding="utf-8"), "do not replace")

    def test_doctor_validates_and_redacts_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "doctor.db")
            output = io.StringIO()
            with patch.dict("os.environ", {
                "OPENAI_API_KEY": "",
                "OPENAI_BASE_URL": "http://127.0.0.1:11434/v1",
                "OPENAI_MODEL": "local-model",
            }, clear=False), redirect_stdout(output):
                self.assertEqual(main(["--db", db, "doctor"]), 0)
            self.assertIn('"api_ready": true', output.getvalue())

            output = io.StringIO()
            with patch.dict("os.environ", {
                "OPENAI_API_KEY": "configured",
                "OPENAI_BASE_URL": "https://example.com/v1?api_key=must-not-leak",
                "OPENAI_MODEL": "model",
            }, clear=False), redirect_stdout(output):
                self.assertEqual(main(["--db", db, "doctor"]), 1)
            self.assertNotIn("must-not-leak", output.getvalue())

            blocker = Path(tmp) / "not-a-directory"
            blocker.write_text("x", encoding="utf-8")
            with patch.dict("os.environ", {
                "OPENAI_API_KEY": "",
                "OPENAI_BASE_URL": "http://127.0.0.1:11434/v1",
                "OPENAI_MODEL": "local-model",
            }, clear=False), redirect_stdout(io.StringIO()):
                self.assertEqual(main(["--db", str(blocker / "db.sqlite"), "doctor"]), 1)


if __name__ == "__main__":
    unittest.main()
