from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from typing import Any, Dict, Iterable, List

import streamlit as st

from models import Task, TaskStatus
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
        series_id=raw.get("series_id"),
        required_environment=tuple(raw.get("required_environment", ())),
        required_quietness=float(raw.get("required_quietness", 0.0)),
        dependencies=tuple(raw.get("dependencies", ())),
        must_be_contiguous=True,
        status=TaskStatus(task_status_value(raw)),
        tags=tuple(raw.get("tags", ())),
    )


def parse_optional_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(str(value))


def active_schedulable_tasks(tasks: Iterable[Task]) -> List[Task]:
    task_list = list(tasks)
    completed_ids = completed_task_ids(task_list)
    return [
        remove_completed_dependencies(task, completed_ids)
        for task in task_list
        if task.status == TaskStatus.PENDING
    ]


def completed_task_ids(tasks: Iterable[Task]) -> set[str]:
    return {task.task_id for task in tasks if task.status == TaskStatus.DONE}


def remove_completed_dependencies(task: Task, completed_ids: set[str]) -> Task:
    return replace(
        task,
        dependencies=tuple(dep for dep in task.dependencies if dep not in completed_ids),
    )


def remove_task(task_id: str) -> None:
    st.session_state.pending_tasks = [
        task for task in st.session_state.pending_tasks if task["task_id"] != task_id
    ]
    remove_stale_dependencies()
    mark_schedule_dirty()


def remove_stale_dependencies() -> None:
    valid_ids = {task["task_id"] for task in st.session_state.pending_tasks}
    for task in st.session_state.pending_tasks:
        task["dependencies"] = tuple(dep for dep in task.get("dependencies", ()) if dep in valid_ids)


def task_status_value(task: Dict[str, Any]) -> str:
    status = str(task.get("status", TaskStatus.PENDING.value))
    try:
        return TaskStatus(status).value
    except ValueError:
        return TaskStatus.PENDING.value

