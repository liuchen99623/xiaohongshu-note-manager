#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path

SKIP_DIRS = {".git", ".venv", "__pycache__", "build", "dist", "data", "exports"}
TEXT_SUFFIXES = {"", ".py", ".md", ".txt", ".toml", ".yml", ".yaml", ".json", ".example", ".gitignore"}
PATTERNS = {
    "GitHub token": re.compile(r"\bgh[opusr]_[A-Za-z0-9_]{20,}\b"),
    "OpenAI-style key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "Private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "Suspicious assignment": re.compile(r'''(?i)(api[_-]?key|access[_-]?token|secret|password)\s*[:=]\s*['"](?!replace-me|your-|<)[^'"]{12,}['"]'''),
}


def main(root: str) -> int:
    findings: list[str] = []
    for path in Path(root).rglob("*"):
        if not path.is_file() or any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in {".env.example", ".gitignore"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for name, pattern in PATTERNS.items():
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                findings.append(f"{path}:{line}: {name}")
    if findings:
        print("Secret scan failed:")
        print("\n".join(findings))
        return 1
    print("Secret scan passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "."))
