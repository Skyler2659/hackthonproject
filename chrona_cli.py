from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

from chrona_service.config import resolve_config
from chrona_service.exceptions import ChronaServiceError
from chrona_service.profile import build_user_profile
from chrona_service.scheduler import read_status, recover_schedule, run_schedule
from chrona_service.store import load_profile_memory, save_profile_memory
from chrona_service.tasks import (
    add_tasks_from_file,
    add_tasks_from_text,
    list_tasks,
    remove_task,
    set_task_status,
)
from chrona_service.web import start_web, web_status


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(normalize_global_args(argv or sys.argv[1:]))
    try:
        config = resolve_config(root=args.root, user=args.user, offline=args.offline)
        payload = dispatch(config, args)
    except ChronaServiceError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print_payload(payload, output_format=args.format)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="chrona", description="Chrona headless CLI for ArkClaw/OpenClaw.")
    parser.add_argument("--root", help="Chrona project root. Defaults to CHRONA_ROOT or auto-detect.")
    parser.add_argument("--user", help="Chrona local user. Defaults to CHRONA_USER or admin.")
    parser.add_argument("--offline", action="store_true", help="Use deterministic mock LLM instead of DeepSeek.")
    parser.add_argument("--format", choices=("json", "text"), default="json")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("status", help="Show task and schedule status.")

    schedule = subparsers.add_parser("schedule", help="Run AI scoring and constraint scheduling.")
    schedule.add_argument("--ensemble-size", type=int, default=3)

    recover = subparsers.add_parser("recover", help="Mark a missed task and reschedule remaining tasks.")
    recover.add_argument("--missed", required=True, help="Task id that was missed.")
    recover.add_argument("--ensemble-size", type=int, default=3)

    task = subparsers.add_parser("task", help="Task operations.")
    task_sub = task.add_subparsers(dest="task_command", required=True)
    task_list = task_sub.add_parser("list", help="List tasks.")
    task_list.add_argument("--status", choices=("pending", "scheduled", "missed", "done", "cancelled"))
    task_add = task_sub.add_parser("add", help="Add tasks from text or JSON.")
    task_add.add_argument("text", nargs="?", help="Natural-language task text.")
    task_add.add_argument("--file", type=Path, help="JSON file containing one task, an array, or {tasks:[...]}.")
    task_done = task_sub.add_parser("done", help="Mark a task done.")
    task_done.add_argument("--id", required=True)
    task_missed = task_sub.add_parser("missed", help="Mark a task missed.")
    task_missed.add_argument("--id", required=True)
    task_remove = task_sub.add_parser("remove", help="Remove a task.")
    task_remove.add_argument("--id", required=True)

    profile = subparsers.add_parser("profile", help="Profile operations.")
    profile_sub = profile.add_subparsers(dest="profile_command", required=True)
    profile_sub.add_parser("show", help="Show profile memory and algorithm profile summary.")
    profile_set = profile_sub.add_parser("set", help="Replace profile memory from JSON.")
    profile_set.add_argument("--file", type=Path, required=True)

    web = subparsers.add_parser("web", help="Streamlit website operations.")
    web_sub = web.add_subparsers(dest="web_command", required=True)
    web_status_parser = web_sub.add_parser("status", help="Show website URL and reachability.")
    web_status_parser.add_argument("--port", type=int, default=8501)
    web_start_parser = web_sub.add_parser("start", help="Start the Streamlit website.")
    web_start_parser.add_argument("--port", type=int, default=8501)
    return parser


def dispatch(config, args) -> Dict[str, Any] | list[Dict[str, Any]]:
    if args.command == "status":
        return read_status(config, include_web=web_status(config))
    if args.command == "schedule":
        return run_schedule(config, ensemble_size=max(1, int(args.ensemble_size)))
    if args.command == "recover":
        return recover_schedule(
            config,
            missed_task_id=args.missed,
            ensemble_size=max(1, int(args.ensemble_size)),
        )
    if args.command == "task":
        return dispatch_task(config, args)
    if args.command == "profile":
        return dispatch_profile(config, args)
    if args.command == "web":
        if args.web_command == "status":
            return web_status(config, port=args.port)
        if args.web_command == "start":
            return start_web(config, port=args.port)
    raise ChronaServiceError("Unknown command.")


def dispatch_task(config, args):
    if args.task_command == "list":
        return list_tasks(config, status=args.status)
    if args.task_command == "add":
        if args.file:
            return add_tasks_from_file(config, args.file)
        if args.text:
            return add_tasks_from_text(config, args.text)
        raise ChronaServiceError("task add requires text or --file.")
    if args.task_command == "done":
        return set_task_status(config, args.id, "done")
    if args.task_command == "missed":
        return set_task_status(config, args.id, "missed")
    if args.task_command == "remove":
        return remove_task(config, args.id)
    raise ChronaServiceError("Unknown task command.")


def dispatch_profile(config, args):
    if args.profile_command == "show":
        memory = load_profile_memory(config.root, config.user)
        profile = build_user_profile(memory, user_id=config.user, generous=True)
        return {
            "memory": memory,
            "algorithm_profile": {
                "user_id": profile.user_id,
                "chronotype": profile.chronotype,
                "available_windows": [[s.strftime("%H:%M"), e.strftime("%H:%M")] for s, e in profile.available_windows],
                "preferred_windows": [[s.strftime("%H:%M"), e.strftime("%H:%M")] for s, e in profile.preferred_windows],
                "quiet_windows": [[s.strftime("%H:%M"), e.strftime("%H:%M")] for s, e in profile.quiet_windows],
                "max_daily_deep_work_min": profile.max_daily_deep_work_min,
                "preferred_environments": list(profile.preferred_environments),
            },
        }
    if args.profile_command == "set":
        try:
            payload = json.loads(args.file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ChronaServiceError(f"Could not read profile JSON file: {args.file}") from exc
        if not isinstance(payload, dict):
            raise ChronaServiceError("Profile JSON must be an object.")
        save_profile_memory(config.root, config.user, payload)
        return {"ok": True, "user": config.user}
    raise ChronaServiceError("Unknown profile command.")


def print_payload(payload: Any, *, output_format: str) -> None:
    if output_format == "text":
        print(as_text(payload))
        return
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def as_text(payload: Any) -> str:
    if isinstance(payload, list):
        return "\n".join(f"{item.get('task_id', '-')}: {item.get('title', '')}" for item in payload if isinstance(item, dict))
    if not isinstance(payload, dict):
        return str(payload)
    if "today_blocks" in payload:
        lines = [
            f"Chrona user: {payload.get('user')}",
            f"Pending: {payload.get('pending_count')} | Unfinished: {payload.get('unfinished_count')} | Missed: {payload.get('missed_count')}",
            f"Last run: {payload.get('last_run_at') or 'never'}",
        ]
        web = payload.get("web") or {}
        if web:
            lines.append(f"Web: {web.get('url')} ({'running' if web.get('running') else 'not running'})")
        for block in payload.get("today_blocks") or []:
            lines.append(f"- {block.get('start')} - {block.get('end')}: {block.get('title')}")
        return "\n".join(lines)
    return json.dumps(payload, ensure_ascii=False, indent=2)


def normalize_global_args(argv: list[str]) -> list[str]:
    """Allow --root/--user/--offline/--format before or after subcommands."""
    with_values = {"--root", "--user", "--format"}
    flags = {"--offline"}
    extracted: list[str] = []
    remaining: list[str] = []
    index = 0
    while index < len(argv):
        item = argv[index]
        if item in with_values and index + 1 < len(argv):
            extracted.extend([item, argv[index + 1]])
            index += 2
            continue
        if any(item.startswith(f"{name}=") for name in with_values):
            extracted.append(item)
            index += 1
            continue
        if item in flags:
            extracted.append(item)
            index += 1
            continue
        remaining.append(item)
        index += 1
    return extracted + remaining


if __name__ == "__main__":
    raise SystemExit(main())
