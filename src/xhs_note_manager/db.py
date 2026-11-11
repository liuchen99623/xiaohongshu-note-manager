from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        existed = self.path.exists()
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 5000")
        if not existed:
            try:
                os.chmod(self.path, 0o600)
            except OSError:
                pass
        return conn

    @contextmanager
    def session(self) -> Iterator[sqlite3.Connection]:
        conn = self.connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init(self) -> None:
        schema = """
        CREATE TABLE IF NOT EXISTS profiles (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL UNIQUE,
          positioning TEXT NOT NULL,
          audience TEXT NOT NULL,
          tone TEXT NOT NULL,
          goals_json TEXT NOT NULL DEFAULT '[]',
          banned_json TEXT NOT NULL DEFAULT '[]',
          assets_json TEXT NOT NULL DEFAULT '[]',
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS briefs (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
          topic TEXT NOT NULL,
          objective TEXT NOT NULL,
          content_type TEXT NOT NULL CHECK(content_type IN ('graphic','video')),
          materials TEXT NOT NULL DEFAULT '',
          constraints TEXT NOT NULL DEFAULT '',
          status TEXT NOT NULL DEFAULT 'draft',
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS packages (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          brief_id INTEGER NOT NULL REFERENCES briefs(id) ON DELETE CASCADE,
          content_type TEXT NOT NULL,
          title TEXT NOT NULL,
          payload_json TEXT NOT NULL,
          model TEXT NOT NULL,
          prompt_version TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS calendar (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
          package_id INTEGER REFERENCES packages(id) ON DELETE SET NULL,
          publish_at TEXT NOT NULL,
          publish_at_utc TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'planned',
          notes TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS reviews (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          package_id INTEGER NOT NULL REFERENCES packages(id) ON DELETE CASCADE,
          metrics_json TEXT NOT NULL,
          lessons TEXT NOT NULL DEFAULT '',
          reviewed_at TEXT NOT NULL,
          UNIQUE(package_id)
        );
        CREATE INDEX IF NOT EXISTS idx_briefs_profile ON briefs(profile_id);
        CREATE INDEX IF NOT EXISTS idx_packages_brief ON packages(brief_id);
        """
        with self.session() as conn:
            conn.executescript(schema)
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(packages)")}
            if "prompt_version" not in columns:
                conn.execute("ALTER TABLE packages ADD COLUMN prompt_version TEXT NOT NULL DEFAULT '1.0'")
            calendar_columns = {row["name"] for row in conn.execute("PRAGMA table_info(calendar)")}
            if "publish_at_utc" not in calendar_columns:
                conn.execute("ALTER TABLE calendar ADD COLUMN publish_at_utc TEXT")
            for row in conn.execute("SELECT id,publish_at FROM calendar WHERE publish_at_utc IS NULL"):
                try:
                    normalized = datetime.fromisoformat(row["publish_at"]).astimezone(UTC).isoformat(timespec="seconds")
                except ValueError:
                    normalized = row["publish_at"]
                conn.execute("UPDATE calendar SET publish_at_utc=? WHERE id=?", (normalized, row["id"]))
            conn.execute("DROP INDEX IF EXISTS idx_calendar_profile_at")
            conn.execute("CREATE INDEX idx_calendar_profile_at ON calendar(profile_id, publish_at_utc)")
            conn.execute("DELETE FROM reviews WHERE id NOT IN (SELECT MAX(id) FROM reviews GROUP BY package_id)")
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_reviews_package_unique ON reviews(package_id)")
            conn.execute("PRAGMA user_version = 2")

    def add_profile(self, *, name: str, positioning: str, audience: str, tone: str,
                    goals: list[str], banned: list[str], assets: list[str]) -> int:
        with self.session() as conn:
            cur = conn.execute(
                "INSERT INTO profiles(name,positioning,audience,tone,goals_json,banned_json,assets_json,created_at) VALUES(?,?,?,?,?,?,?,?)",
                (name, positioning, audience, tone, json.dumps(goals, ensure_ascii=False),
                 json.dumps(banned, ensure_ascii=False), json.dumps(assets, ensure_ascii=False), utc_now()),
            )
            return int(cur.lastrowid)

    def list_profiles(self) -> list[dict[str, Any]]:
        with self.session() as conn:
            return [self._decode_profile(r) for r in conn.execute("SELECT * FROM profiles ORDER BY id")]

    def get_profile(self, profile_id: int) -> dict[str, Any]:
        with self.session() as conn:
            row = conn.execute("SELECT * FROM profiles WHERE id=?", (profile_id,)).fetchone()
        if row is None:
            raise KeyError(f"账号档案不存在: {profile_id}")
        return self._decode_profile(row)

    @staticmethod
    def _decode_profile(row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        for source, target in (("goals_json", "goals"), ("banned_json", "banned"), ("assets_json", "assets")):
            data[target] = json.loads(data.pop(source))
        return data

    def add_brief(self, *, profile_id: int, topic: str, objective: str, content_type: str,
                  materials: str = "", constraints: str = "") -> int:
        if content_type not in {"graphic", "video"}:
            raise ValueError("content_type 必须是 graphic 或 video")
        self.get_profile(profile_id)
        with self.session() as conn:
            cur = conn.execute(
                "INSERT INTO briefs(profile_id,topic,objective,content_type,materials,constraints,created_at) VALUES(?,?,?,?,?,?,?)",
                (profile_id, topic, objective, content_type, materials, constraints, utc_now()),
            )
            return int(cur.lastrowid)

    def list_briefs(self, profile_id: int | None = None) -> list[dict[str, Any]]:
        sql, params = "SELECT * FROM briefs", ()
        if profile_id is not None:
            sql, params = sql + " WHERE profile_id=?", (profile_id,)
        with self.session() as conn:
            return [dict(r) for r in conn.execute(sql + " ORDER BY id", params)]

    def get_brief(self, brief_id: int) -> dict[str, Any]:
        with self.session() as conn:
            row = conn.execute("SELECT * FROM briefs WHERE id=?", (brief_id,)).fetchone()
        if row is None:
            raise KeyError(f"内容简报不存在: {brief_id}")
        return dict(row)

    def add_package(self, *, brief_id: int, content_type: str, title: str,
                    payload: dict[str, Any], model: str, prompt_version: str) -> int:
        with self.session() as conn:
            cur = conn.execute(
                "INSERT INTO packages(brief_id,content_type,title,payload_json,model,prompt_version,created_at) VALUES(?,?,?,?,?,?,?)",
                (brief_id, content_type, title, json.dumps(payload, ensure_ascii=False), model, prompt_version, utc_now()),
            )
            return int(cur.lastrowid)

    def get_package(self, package_id: int) -> dict[str, Any]:
        with self.session() as conn:
            row = conn.execute("SELECT * FROM packages WHERE id=?", (package_id,)).fetchone()
        if row is None:
            raise KeyError(f"内容包不存在: {package_id}")
        data = dict(row)
        data["payload"] = json.loads(data.pop("payload_json"))
        return data

    def list_packages(self, profile_id: int | None = None) -> list[dict[str, Any]]:
        sql = "SELECT p.id,p.brief_id,p.content_type,p.title,p.model,p.prompt_version,p.created_at,b.profile_id FROM packages p JOIN briefs b ON b.id=p.brief_id"
        params: tuple[Any, ...] = ()
        if profile_id is not None:
            sql += " WHERE b.profile_id=?"
            params = (profile_id,)
        with self.session() as conn:
            return [dict(r) for r in conn.execute(sql + " ORDER BY p.id", params)]

    def add_calendar(self, *, profile_id: int, package_id: int | None, publish_at: str,
                     status: str = "planned", notes: str = "") -> int:
        self.get_profile(profile_id)
        try:
            scheduled = datetime.fromisoformat(publish_at)
        except ValueError as exc:
            raise ValueError("publish_at 必须是 ISO 8601 时间") from exc
        if scheduled.tzinfo is None:
            raise ValueError("publish_at 必须包含时区，例如 +08:00")
        publish_at_utc = scheduled.astimezone(UTC).isoformat(timespec="seconds")
        if package_id is not None:
            package = self.get_package(package_id)
            brief = self.get_brief(int(package["brief_id"]))
            if int(brief["profile_id"]) != profile_id:
                raise ValueError("内容包不属于指定账号档案")
        with self.session() as conn:
            cur = conn.execute(
                "INSERT INTO calendar(profile_id,package_id,publish_at,publish_at_utc,status,notes,created_at) VALUES(?,?,?,?,?,?,?)",
                (profile_id, package_id, publish_at, publish_at_utc, status, notes, utc_now()),
            )
            return int(cur.lastrowid)

    def list_calendar(self, profile_id: int | None = None) -> list[dict[str, Any]]:
        sql, params = "SELECT * FROM calendar", ()
        if profile_id is not None:
            sql, params = sql + " WHERE profile_id=?", (profile_id,)
        with self.session() as conn:
            return [dict(r) for r in conn.execute(sql + " ORDER BY publish_at_utc,id", params)]

    def add_review(self, *, package_id: int, metrics: dict[str, int], lessons: str = "") -> int:
        self.get_package(package_id)
        if any(not isinstance(value, int) or value < 0 for value in metrics.values()):
            raise ValueError("复盘指标必须是非负整数")
        with self.session() as conn:
            conn.execute(
                """INSERT INTO reviews(package_id,metrics_json,lessons,reviewed_at) VALUES(?,?,?,?)
                   ON CONFLICT(package_id) DO UPDATE SET
                     metrics_json=excluded.metrics_json,
                     lessons=excluded.lessons,
                     reviewed_at=excluded.reviewed_at""",
                (package_id, json.dumps(metrics, ensure_ascii=False), lessons, utc_now()),
            )
            row = conn.execute("SELECT id FROM reviews WHERE package_id=?", (package_id,)).fetchone()
            return int(row["id"])

    def review_summary(self, profile_id: int | None = None) -> dict[str, Any]:
        sql = "SELECT r.metrics_json FROM reviews r JOIN packages p ON p.id=r.package_id JOIN briefs b ON b.id=p.brief_id"
        params: tuple[Any, ...] = ()
        if profile_id is not None:
            sql += " WHERE b.profile_id=?"
            params = (profile_id,)
        totals: dict[str, int] = {}
        count = 0
        with self.session() as conn:
            rows = conn.execute(sql, params).fetchall()
        for row in rows:
            count += 1
            for key, value in json.loads(row["metrics_json"]).items():
                totals[key] = totals.get(key, 0) + int(value)
        reads = totals.get("reads", 0)
        impressions = totals.get("impressions", 0)
        interactions = sum(totals.get(key, 0) for key in ("likes", "comments", "saves", "shares"))
        rates: dict[str, float] = {}
        if impressions:
            rates["read_rate"] = round(reads / impressions, 4)
        if reads:
            rates["interaction_rate"] = round(interactions / reads, 4)
            rates["save_rate"] = round(totals.get("saves", 0) / reads, 4)
            rates["follow_rate"] = round(totals.get("follows", 0) / reads, 4)
            rates["conversion_rate"] = round(totals.get("conversions", 0) / reads, 4)
        return {"review_count": count, "totals": totals, "rates": rates}
