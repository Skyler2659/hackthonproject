from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from typing import Any, Dict, Iterable, List

import streamlit as st

from models import DeadlineType, Task, TaskStatus
from web_ui.archive import record_operation, save_session_archive
from web_ui.session_state import mark_schedule_dirty


def materialize_tasks(raw_tasks: Iterable[Dict[str, Any]]) -> List[Task]:
    return [materialize_task(raw) for raw in raw_tasks]


def materialize_task(raw: Dict[str, Any]) -> Task:
    return Task(
        task_id=raw["task_id"],
        title=raw["title"],
        description=raw.get("description", ""),
        duration_min=int(raw["duration_min"]),
        deadline=datetime.fromisoformat(raw["deadline"]),
        earliest_start=parse_optional_datetime(raw.get("earliest_start")),
        manual_start=parse_optional_datetime(raw.get("manual_start")),
        manual_end=parse_optional_datetime(raw.get("manual_end")),
        series_id=raw.get("series_id"),
        required_environment=tuple(raw.get("required_environment", ())),
        required_quietness=float(raw.get("required_quietness", 0.0)),
        dependencies=tuple(raw.get("dependencies", ())),
        must_be_contiguous=bool(raw.get("must_be_contiguous", True)),
        status=TaskStatus(task_status_value(raw)),
        tags=tuple(raw.get("tags", ())),
        deadline_type=deadline_type_value(raw),
        deep_work_min=parse_optional_deep_work_min(raw),
    )


def parse_optional_deep_work_min(raw: Dict[str, Any]) -> int | None:
    if "deep_work_min" not in raw:
        return None
    value = raw.get("deep_work_min")
    if value is None:
        return None
    return max(0, int(value))


def parse_optional_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(str(value))


def active_schedulable_tasks(tasks: Iterable[Task]) -> List[Task]:
    task_list = list(tasks)
    resolved_ids = resolved_dependency_ids(task_list)
    return [
        remove_resolved_dependencies(task, resolved_ids)
        for task in task_list
        if task.status == TaskStatus.PENDING
    ]


def completed_task_ids(tasks: Iterable[Task]) -> set[str]:
    return {task.task_id for task in tasks if task.status == TaskStatus.DONE}


def resolved_dependency_ids(tasks: Iterable[Task]) -> set[str]:
    return {
        task.task_id
        for task in tasks
        if task.status in {TaskStatus.DONE, TaskStatus.MISSED, TaskStatus.CANCELLED}
    }


def remove_resolved_dependencies(task: Task, resolved_ids: set[str]) -> Task:
    return replace(
        task,
        dependencies=tuple(dep for dep in task.dependencies if dep not in resolved_ids),
    )


def remove_task(task_id: str) -> None:
    removed_task = next(
        (task for task in st.session_state.pending_tasks if task["task_id"] == task_id),
        None,
    )
    st.session_state.pending_tasks = [
        task for task in st.session_state.pending_tasks if task["task_id"] != task_id
    ]
    remove_stale_dependencies()
    if removed_task:
        record_operation("task_removed", task_id=task_id, title=str(removed_task.get("title", "")))
    else:
        save_session_archive()
    mark_schedule_dirty()


def remove_stale_dependencies() -> None:
    valid_ids = {task["task_id"] for task in st.session_state.pending_tasks}
    for task in st.session_state.pending_tasks:
        task["dependencies"] = tuple(dep for dep in task.get("dependencies", ()) if dep in valid_ids)


def clear_tasks() -> None:
    removed_count = len(st.session_state.pending_tasks)
    st.session_state.pending_tasks = []
    record_operation("task_list_cleared", detail=f"removed_count={removed_count}")
    mark_schedule_dirty()


def mark_overdue_tasks_missed(now: datetime) -> List[str]:
    missed_task_ids: List[str] = []
    for task in st.session_state.pending_tasks:
        if task_status_value(task) != TaskStatus.PENDING.value:
            continue
        if datetime.fromisoformat(task["deadline"]) > now:
            task["deadline_overdue"] = False
            continue
        if deadline_type_value(task) == DeadlineType.STRICT:
            task["status"] = TaskStatus.MISSED.value
            missed_task_ids.append(str(task["task_id"]))
            record_operation(
                "task_missed",
                task_id=str(task["task_id"]),
                title=str(task.get("title", "")),
                detail="strict deadline passed",
            )
        elif not task.get("deadline_overdue"):
            task["deadline_overdue"] = True
            missed_task_ids.append(str(task["task_id"]))
            record_operation(
                "task_overdue_flexible",
                task_id=str(task["task_id"]),
                title=str(task.get("title", "")),
                detail="flexible deadline passed; kept pending",
            )
    if missed_task_ids:
        mark_schedule_dirty()
    return missed_task_ids


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
