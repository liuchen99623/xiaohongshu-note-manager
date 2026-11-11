from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import tempfile
import urllib.parse
from pathlib import Path
from typing import Any

from .config import Settings
from .db import Database
from .llm import LLMError, OpenAICompatibleClient
from .workflow import ContentWorkflow, package_to_markdown


def csv_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def redacted_base_url(value: str) -> str:
    try:
        parsed = urllib.parse.urlsplit(value)
        if not parsed.scheme or not parsed.hostname:
            return "[invalid]"
        host = f"[{parsed.hostname}]" if ":" in parsed.hostname else parsed.hostname
        if parsed.port:
            host += f":{parsed.port}"
        return urllib.parse.urlunsplit((parsed.scheme, host, parsed.path, "", ""))
    except ValueError:
        return "[invalid]"


def path_is_writable(path: Path) -> bool:
    if path.exists():
        return path.is_file() and os.access(path, os.W_OK)
    current = path.parent
    while not current.exists() and current != current.parent:
        current = current.parent
    return current.is_dir() and os.access(current, os.W_OK)


def write_secure_text(output: Path, content: str, *, force: bool) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.is_symlink():
        raise ValueError("拒绝写入符号链接")
    if force:
        descriptor, temp_name = tempfile.mkstemp(prefix=f".{output.name}.", dir=output.parent)
        temp_path = Path(temp_name)
        try:
            os.chmod(temp_path, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, output)
        finally:
            temp_path.unlink(missing_ok=True)
        return
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(output, flags, 0o600)
    except FileExistsError as exc:
        raise ValueError("输出文件已存在；确认覆盖时请添加 --force") from exc
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(content)


def add_parsers(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--db", help="SQLite 路径；默认读取 XHS_MANAGER_DB")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init", help="初始化本地数据库")
    sub.add_parser("doctor", help="检查运行环境（不会输出密钥）")

    profile = sub.add_parser("profile", help="管理账号档案")
    psub = profile.add_subparsers(dest="action", required=True)
    pa = psub.add_parser("add", help="新增账号档案")
    pa.add_argument("--name", required=True)
    pa.add_argument("--positioning", required=True)
    pa.add_argument("--audience", required=True)
    pa.add_argument("--tone", default="自然、真诚、实用")
    pa.add_argument("--goals", default="涨粉,互动")
    pa.add_argument("--banned", default="")
    pa.add_argument("--assets", default="")
    psub.add_parser("list", help="列出账号档案")
    ps = psub.add_parser("show", help="查看账号档案")
    ps.add_argument("id", type=int)

    brief = sub.add_parser("brief", help="管理内容简报")
    bsub = brief.add_subparsers(dest="action", required=True)
    ba = bsub.add_parser("add", help="新增内容简报")
    ba.add_argument("--profile", type=int, required=True)
    ba.add_argument("--topic", required=True)
    ba.add_argument("--objective", required=True, choices=["涨粉", "互动", "品牌认知", "私信咨询", "店铺访问", "销售"])
    ba.add_argument("--type", dest="content_type", required=True, choices=["graphic", "video"])
    ba.add_argument("--materials", default="")
    ba.add_argument("--constraints", default="")
    bl = bsub.add_parser("list", help="列出内容简报")
    bl.add_argument("--profile", type=int)
    bs = bsub.add_parser("show", help="查看内容简报")
    bs.add_argument("id", type=int)

    prompt = sub.add_parser("prompt", help="预览将发送给模型的提示词")
    prompt.add_argument("--brief", type=int, required=True)

    generate = sub.add_parser("generate", help="调用模型生成并保存内容包")
    generate.add_argument("--brief", type=int, required=True)

    package = sub.add_parser("package", help="查看内容包")
    pksub = package.add_subparsers(dest="action", required=True)
    pkl = pksub.add_parser("list")
    pkl.add_argument("--profile", type=int)
    pks = pksub.add_parser("show")
    pks.add_argument("id", type=int)

    export = sub.add_parser("export", help="导出内容包")
    export.add_argument("--package", type=int, required=True)
    export.add_argument("--format", choices=["md", "json"], default="md")
    export.add_argument("--output", required=True)
    export.add_argument("--force", action="store_true", help="允许覆盖已有普通文件")

    calendar = sub.add_parser("calendar", help="管理内容排期；不执行自动发布")
    csub = calendar.add_subparsers(dest="action", required=True)
    ca = csub.add_parser("add")
    ca.add_argument("--profile", type=int, required=True)
    ca.add_argument("--package", type=int)
    ca.add_argument("--at", required=True, help="ISO 时间，例如 2026-11-15T20:00:00+08:00")
    ca.add_argument("--status", default="planned", choices=["planned", "ready", "published", "cancelled"])
    ca.add_argument("--notes", default="")
    cl = csub.add_parser("list")
    cl.add_argument("--profile", type=int)

    review = sub.add_parser("review", help="记录真实发布数据并汇总")
    rsub = review.add_subparsers(dest="action", required=True)
    ra = rsub.add_parser("add")
    ra.add_argument("--package", type=int, required=True)
    for metric in ("impressions", "reads", "likes", "comments", "saves", "shares", "follows", "profile_visits", "conversions"):
        ra.add_argument(f"--{metric.replace('_', '-')}", type=int, default=0)
    ra.add_argument("--lessons", default="")
    rs = rsub.add_parser("summary")
    rs.add_argument("--profile", type=int)


def run(args: argparse.Namespace) -> int:
    settings = Settings.from_env(args.db)
    db = Database(settings.db_path)
    if args.command == "doctor":
        errors: list[str] = []
        python_ok = sys.version_info >= (3, 11)
        if not python_ok:
            errors.append("需要 Python 3.11 或更高版本")
        db_writable = path_is_writable(settings.db_path)
        if not db_writable:
            errors.append("数据库路径不可写")
        client_ok = True
        api_ready = False
        try:
            OpenAICompatibleClient(
                api_key=settings.api_key,
                base_url=settings.base_url,
                model=settings.model,
                timeout=settings.timeout,
            )
            hostname = urllib.parse.urlsplit(settings.base_url).hostname
            api_ready = bool(settings.api_key) or hostname in {"localhost", "127.0.0.1", "::1"}
            if not api_ready:
                errors.append("远程模型端点需要 OPENAI_API_KEY")
        except LLMError as exc:
            client_ok = False
            errors.append(str(exc))
        result = {
            "python": sys.version.split()[0],
            "python_ok": python_ok,
            "db_path": str(settings.db_path),
            "db_path_writable": db_writable,
            "api_key_configured": bool(settings.api_key),
            "api_ready": api_ready,
            "client_config_ok": client_ok,
            "base_url": redacted_base_url(settings.base_url),
            "model": settings.model,
            "errors": errors,
        }
        print_json(result)
        return 0 if not errors else 1
    db.init()
    if args.command == "init":
        print(f"数据库已初始化：{settings.db_path}")
    elif args.command == "profile":
        if args.action == "add":
            ident = db.add_profile(name=args.name, positioning=args.positioning, audience=args.audience,
                                   tone=args.tone, goals=csv_list(args.goals), banned=csv_list(args.banned), assets=csv_list(args.assets))
            print(f"账号档案已创建：{ident}")
        elif args.action == "list": print_json(db.list_profiles())
        else: print_json(db.get_profile(args.id))
    elif args.command == "brief":
        if args.action == "add":
            ident = db.add_brief(profile_id=args.profile, topic=args.topic, objective=args.objective,
                                 content_type=args.content_type, materials=args.materials, constraints=args.constraints)
            print(f"内容简报已创建：{ident}")
        elif args.action == "list": print_json(db.list_briefs(args.profile))
        else: print_json(db.get_brief(args.id))
    elif args.command in {"prompt", "generate"}:
        client = OpenAICompatibleClient(api_key=settings.api_key, base_url=settings.base_url, model=settings.model, timeout=settings.timeout)
        flow = ContentWorkflow(db, client, settings.model)
        if args.command == "prompt":
            print(flow.prompt_for(args.brief))
        else:
            ident = flow.generate(args.brief)
            print(f"内容包已生成：{ident}")
    elif args.command == "package":
        print_json(db.list_packages(args.profile) if args.action == "list" else db.get_package(args.id))
    elif args.command == "export":
        package = db.get_package(args.package)
        output = Path(args.output).expanduser()
        content = package_to_markdown(package) if args.format == "md" else json.dumps(package, ensure_ascii=False, indent=2) + "\n"
        write_secure_text(output, content, force=args.force)
        print(f"已导出：{output}")
    elif args.command == "calendar":
        if args.action == "add":
            ident = db.add_calendar(profile_id=args.profile, package_id=args.package, publish_at=args.at,
                                    status=args.status, notes=args.notes)
            print(f"排期已创建：{ident}（仅记录，不会自动发布）")
        else: print_json(db.list_calendar(args.profile))
    elif args.command == "review":
        if args.action == "add":
            metrics = {key: getattr(args, key) for key in ("impressions", "reads", "likes", "comments", "saves", "shares", "follows", "profile_visits", "conversions")}
            ident = db.add_review(package_id=args.package, metrics=metrics, lessons=args.lessons)
            print(f"复盘记录已创建：{ident}")
        else: print_json(db.review_summary(args.profile))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="xhs-note-manager", description="小红书笔记管家：从账号定位到内容复盘的本地工作流")
    add_parsers(parser)
    args = parser.parse_args(argv)
    try:
        return run(args)
    except (KeyError, ValueError, LLMError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2
    except (OSError, sqlite3.Error) as exc:
        print(f"系统错误：{exc}", file=sys.stderr)
        return 3
    except KeyboardInterrupt:
        print("已取消", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
