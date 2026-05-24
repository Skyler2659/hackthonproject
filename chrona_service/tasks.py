from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List

from agents import TaskParserAgent
from chrona_service.config import ChronaConfig
from chrona_service.exceptions import ChronaServiceError
from chrona_service.llm import build_llm_client
from chrona_service.profile import build_user_profile
from chrona_service.serializers import parse_optional_datetime
from chrona_service.store import append_operation, load_archive, load_profile_memory, save_archive
from models import DeadlineType, Task, TaskStatus, UserProfile, clamp01


ENVIRONMENT_OPTIONS = ["desk", "library", "classroom", "meeting_room", "mobile", "online"]


def materialize_tasks(raw_tasks: Iterable[Dict[str, Any]]) -> List[Task]:
    return [materialize_task(raw) for raw in raw_tasks]


def materialize_task(raw: Dict[str, Any]) -> Task:
    return Task(
        task_id=str(raw["task_id"]),
        title=str(raw["title"]),
        description=str(raw.get("description", "")),
        duration_min=int(raw["duration_min"]),
        deadline=datetime.fromisoformat(str(raw["deadline"])),
        earliest_start=parse_optional_datetime(raw.get("earliest_start")),
        manual_start=parse_optional_datetime(raw.get("manual_start")),
        manual_end=parse_optional_datetime(raw.get("manual_end")),
        series_id=normalized_text(raw.get("series_id")) or None,
        required_environment=tuple(normalize_string_list(raw.get("required_environment"))),
        required_quietness=float(raw.get("required_quietness", 0.0)),
        dependencies=tuple(normalize_string_list(raw.get("dependencies"))),
        must_be_contiguous=normalize_bool(raw.get("must_be_contiguous"), True),
        status=TaskStatus(task_status_value(raw)),
        tags=tuple(normalize_string_list(raw.get("tags"))),
        deadline_type=deadline_type_value(raw),
        deep_work_min=parse_optional_int(raw.get("deep_work_min")),
    )


def active_schedulable_tasks(tasks: Iterable[Task]) -> List[Task]:
    from algorithms.task_selection import prepare_schedulable_tasks

    return prepare_schedulable_tasks(tasks)


def task_status_value(task: Dict[str, Any]) -> str:
    status = str(task.get("status", TaskStatus.PENDING.value))
    try:
        return TaskStatus(status).value
    except ValueError:
        return TaskStatus.PENDING.value


def deadline_type_value(task: Dict[str, Any]) -> DeadlineType:
    try:
        return DeadlineType(str(task.get("deadline_type", DeadlineType.FLEXIBLE.value)))
    except ValueError:
        return DeadlineType.FLEXIBLE


def list_tasks(config: ChronaConfig, *, status: str | None = None) -> List[Dict[str, Any]]:
    archive = load_archive(config.root, config.user)
    rows = list(archive.get("pending_tasks") or [])
    if status:
        rows = [task for task in rows if task_status_value(task) == status]
    return rows


def set_task_status(config: ChronaConfig, task_id: str, status: str) -> Dict[str, Any]:
    next_status = TaskStatus(status).value
    archive = load_archive(config.root, config.user)
    for task in archive.get("pending_tasks", []):
        if str(task.get("task_id")) != task_id:
            continue
        previous = task_status_value(task)
        task["status"] = next_status
        append_operation(
            archive,
            "task_status_changed",
            task_id=task_id,
            title=str(task.get("title", "")),
            detail=f"{previous}->{next_status}",
        )
        clear_schedule_cache(archive)
        save_archive(config.root, config.user, archive)
        return {"task_id": task_id, "previous_status": previous, "status": next_status}
    raise ChronaServiceError(f"Task not found: {task_id}")


def remove_task(config: ChronaConfig, task_id: str) -> Dict[str, Any]:
    archive = load_archive(config.root, config.user)
    tasks = list(archive.get("pending_tasks") or [])
    removed = next((task for task in tasks if str(task.get("task_id")) == task_id), None)
    if removed is None:
        raise ChronaServiceError(f"Task not found: {task_id}")
    archive["pending_tasks"] = [task for task in tasks if str(task.get("task_id")) != task_id]
    remove_stale_dependencies(archive["pending_tasks"])
    append_operation(
        archive,
        "task_removed",
        task_id=task_id,
        title=str(removed.get("title", "")),
    )
    clear_schedule_cache(archive)
    save_archive(config.root, config.user, archive)
    return {"ok": True, "removed_task_id": task_id}


def add_tasks_from_file(config: ChronaConfig, path: Path) -> Dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ChronaServiceError(f"Could not read task JSON file: {path}") from exc
    if isinstance(raw, dict) and isinstance(raw.get("tasks"), list):
        raw_tasks = raw["tasks"]
    elif isinstance(raw, list):
        raw_tasks = raw
    elif isinstance(raw, dict):
        raw_tasks = [raw]
    else:
        raise ChronaServiceError("Task file must contain an object, array, or {\"tasks\": [...]}.")
    return add_task_payloads(config, [dict(item) for item in raw_tasks if isinstance(item, dict)])


def add_tasks_from_text(config: ChronaConfig, text: str) -> Dict[str, Any]:
    archive = load_archive(config.root, config.user)
    memory = load_profile_memory(config.root, config.user)
    now = datetime.now().replace(second=0, microsecond=0)
    profile = build_user_profile(memory, user_id=config.user, generous=False)
    existing = materialize_tasks(archive.get("pending_tasks") or [])
    parsed = TaskParserAgent(llm_client=build_llm_client(config)).parse_task(
        user_text=text,
        profile=profile,
        now=now,
        allowed_environment_options=ENVIRONMENT_OPTIONS,
        existing_tasks=existing,
    )
    raw_tasks = parsed.get("tasks") if isinstance(parsed, dict) else None
    if not isinstance(raw_tasks, list) or not raw_tasks:
        raise ChronaServiceError("Task parser returned no tasks.")
    payloads = normalize_new_task_payloads(
        [dict(item) for item in raw_tasks if isinstance(item, dict)],
        source_text=text,
        now=now,
        existing_tasks=archive.get("pending_tasks") or [],
    )
    return add_task_payloads(config, payloads, already_normalized=True)


def add_task_payloads(
    config: ChronaConfig,
    payloads: List[Dict[str, Any]],
    *,
    already_normalized: bool = False,
) -> Dict[str, Any]:
    archive = load_archive(config.root, config.user)
    now = datetime.now().replace(second=0, microsecond=0)
    tasks = (
        payloads
        if already_normalized
        else normalize_new_task_payloads(
            payloads,
            source_text="",
            now=now,
            existing_tasks=archive.get("pending_tasks") or [],
        )
    )
    archive.setdefault("pending_tasks", [])
    archive["pending_tasks"].extend(tasks)
    for task in tasks:
        append_operation(
            archive,
            "task_added",
            task_id=str(task["task_id"]),
            title=str(task["title"]),
            detail=f"duration_min={task['duration_min']}",
        )
    clear_schedule_cache(archive)
    save_archive(config.root, config.user, archive)
    return {"added_task_ids": [str(task["task_id"]) for task in tasks], "tasks": tasks}


def normalize_new_task_payloads(
    raw_tasks: List[Dict[str, Any]],
    *,
    source_text: str,
    now: datetime,
    existing_tasks: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    used_ids = {str(task.get("task_id")) for task in existing_tasks}
    id_map: Dict[str, str] = {}
    for raw in raw_tasks:
        old_id = normalized_text(raw.get("task_id"))
        new_id = unique_task_id(normalized_text(raw.get("title")) or source_text[:28] or "task", used_ids)
        if old_id:
            id_map[old_id] = new_id
        used_ids.add(new_id)
    return [
        normalize_new_task_payload(raw, source_text=source_text, now=now, id_map=id_map, used_ids=used_ids)
        for raw in raw_tasks
    ]


def normalize_new_task_payload(
    raw: Dict[str, Any],
    *,
    source_text: str,
    now: datetime,
    id_map: Dict[str, str],
    used_ids: set[str],
) -> Dict[str, Any]:
    title = normalized_text(raw.get("title")) or source_text[:28] or "新任务"
    old_id = normalized_text(raw.get("task_id"))
    task_id = id_map.get(old_id) or unique_task_id(title, used_ids)
    fixed_start = parse_optional_datetime(raw.get("fixed_start") or raw.get("manual_start") or raw.get("start"))
    fixed_end = parse_optional_datetime(raw.get("fixed_end") or raw.get("manual_end") or raw.get("end"))
    if fixed_start and fixed_end and fixed_start < fixed_end:
        duration_min = int((fixed_end - fixed_start).total_seconds() // 60)
        deadline = fixed_end
        earliest_start = fixed_start
        deadline_type = DeadlineType.STRICT.value
        manual_start = fixed_start
        manual_end = fixed_end
    else:
        duration_min = normalize_duration(raw.get("duration_min"))
        deadline = parse_optional_datetime(raw.get("deadline")) or default_deadline(now)
        earliest_start = parse_optional_datetime(raw.get("earliest_start")) or now
        deadline_type = normalize_deadline_type(raw.get("deadline_type")).value
        manual_start = None
        manual_end = None
    dependencies = [
        id_map.get(dep, dep)
        for dep in normalize_string_list(raw.get("dependencies"))
        if id_map.get(dep, dep)
    ]
    return {
        "task_id": task_id,
        "title": title,
        "description": normalized_text(raw.get("description")) or source_text,
        "series_id": normalized_text(raw.get("series_id")) or None,
        "duration_min": max(5, duration_min),
        "deadline": deadline.replace(second=0, microsecond=0).isoformat(),
        "deadline_type": deadline_type,
        "earliest_start": earliest_start.replace(second=0, microsecond=0).isoformat(),
        "manual_start": manual_start.replace(second=0, microsecond=0).isoformat() if manual_start else None,
        "manual_end": manual_end.replace(second=0, microsecond=0).isoformat() if manual_end else None,
        "required_environment": normalize_environments(raw.get("required_environment")),
        "required_quietness": normalize_score(raw.get("required_quietness"), default=0.45),
        "dependencies": tuple(dict.fromkeys(dependencies)),
        "must_be_contiguous": normalize_bool(raw.get("must_be_contiguous"), True),
        "deep_work_min": normalize_deep_work_min(raw.get("deep_work_min"), duration_min),
        "status": TaskStatus.PENDING.value,
        "tags": tuple(normalize_string_list(raw.get("tags")))[:8],
    }


def clear_schedule_cache(archive: Dict[str, Any]) -> None:
    archive["last_scores"] = None
    archive["last_result"] = None
    archive["last_profile"] = None
    archive["last_run_at"] = None


def remove_stale_dependencies(tasks: List[Dict[str, Any]]) -> None:
    valid_ids = {str(task.get("task_id")) for task in tasks}
    for task in tasks:
        task["dependencies"] = tuple(dep for dep in normalize_string_list(task.get("dependencies")) if dep in valid_ids)


def unique_task_id(title: str, used_ids: set[str]) -> str:
    while True:
        candidate = make_task_id(title)
        if candidate not in used_ids:
            return candidate


def make_task_id(title: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", title.strip().lower()).strip("-") or "task"
    return f"{slug[:28]}-{uuid.uuid4().hex[:6]}"


def default_deadline(now: datetime) -> datetime:
    return (now + timedelta(days=3)).replace(hour=23, minute=59, second=0, microsecond=0)


def normalize_duration(value: Any) -> int:
    try:
        duration = int(round(float(value) / 5) * 5)
    except (TypeError, ValueError):
        duration = 30
    return max(5, min(480, duration))


def normalize_score(value: Any, default: float) -> float:
    try:
        return clamp01(float(value))
    except (TypeError, ValueError):
        return clamp01(default)


def normalize_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    raw = normalized_text(value).lower()
    if raw in {"true", "1", "yes", "y", "是", "需要", "整块"}:
        return True
    if raw in {"false", "0", "no", "n", "否", "不需要", "可中断"}:
        return False
    return default


def normalize_deadline_type(value: Any) -> DeadlineType:
    raw = normalized_text(value).lower()
    if raw in {"strict", "hard", "严格", "严格截止"}:
        return DeadlineType.STRICT
    return DeadlineType.FLEXIBLE


def normalize_environments(value: Any) -> List[str]:
    environments = [item for item in normalize_string_list(value) if item in ENVIRONMENT_OPTIONS]
    return environments or ["desk"]


def normalize_deep_work_min(value: Any, duration_min: int) -> int | None:
    parsed = parse_optional_int(value)
    if parsed is None:
        return None
    return max(0, min(parsed, duration_min))


def parse_optional_int(value: Any) -> int | None:
    if value is None or str(value).strip().lower() == "null":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def normalize_string_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw_items = value.split(",")
    elif isinstance(value, (list, tuple)):
        raw_items = value
    else:
        raw_items = [value]
    return [str(item).strip() for item in raw_items if str(item).strip()]


def normalized_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() == "null" else text
