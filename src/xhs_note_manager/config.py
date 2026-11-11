from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path


def default_db_path() -> Path:
    if value := os.getenv("XDG_DATA_HOME"):
        root = Path(value).expanduser()
    elif sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support"
    elif os.name == "nt" and (value := os.getenv("APPDATA")):
        root = Path(value).expanduser()
    else:
        root = Path.home() / ".local" / "share"
    return root / "xiaohongshu-note-manager" / "manager.db"


@dataclass(frozen=True)
class Settings:
    api_key: str
    base_url: str
    model: str
    db_path: Path
    timeout: int

    @classmethod
    def from_env(cls, db_override: str | None = None) -> "Settings":
        return cls(
            api_key=os.getenv("OPENAI_API_KEY", "").strip(),
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
            model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip(),
            db_path=Path(db_override or os.getenv("XHS_MANAGER_DB") or default_db_path()).expanduser(),
            timeout=int(os.getenv("XHS_MANAGER_TIMEOUT", "90")),
        )
