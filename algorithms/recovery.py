from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
from typing import List, Set

from core.models import Task, TaskStatus


class RecoveryEngine:
    """Computes the local subset touched by a disruption event."""

    def __init__(self, recovery_window_hours: int = 8) -> None:
        self.recovery_window_hours = recovery_window_hours

    def affected_task_ids(
        self,
        missed_task_id: str,
        tasks: List[Task],
        now: datetime | None = None,
    ) -> Set[str]:
        return affected_task_ids(
            missed_task_id=missed_task_id,
            tasks=tasks,
            now=now,
            recovery_window_hours=self.recovery_window_hours,
        )

    def recovery_tasks(
        self,
        missed_task_id: str,
        tasks: List[Task],
        now: datetime,
    ) -> List[Task]:
        affected_ids = self.affected_task_ids(missed_task_id, tasks, now)
        return [
            relax_recovery_dependencies(task, affected_ids, missed_task_id)
            for task in tasks
            if task.task_id in affected_ids
            and task.task_id != missed_task_id
            and task.status in {TaskStatus.PENDING, TaskStatus.SCHEDULED}
        ]


def affected_task_ids(
    missed_task_id: str,
    tasks: List[Task],
    now: datetime | None = None,
    recovery_window_hours: int = 8,
) -> Set[str]:
    by_id = {task.task_id: task for task in tasks}
    affected = {missed_task_id}
    series_id = by_id[missed_task_id].series_id if missed_task_id in by_id else None

    changed = True
    while changed:
        changed = extend_affected_tasks(affected, series_id, tasks)
    if now is not None:
        affected.update(tasks_in_recovery_window(tasks, now, recovery_window_hours))
    return affected


def extend_affected_tasks(affected: Set[str], series_id: str | None, tasks: List[Task]) -> bool:
    changed = False
    for task in tasks:
        depends_on_affected = bool(set(task.dependencies) & affected)
        same_series = bool(series_id and task.series_id == series_id)
        if (depends_on_affected or same_series) and task.task_id not in affected:
            affected.add(task.task_id)
            changed = True
    return changed


def tasks_in_recovery_window(
    tasks: List[Task],
    now: datetime,
    recovery_window_hours: int = 8,
) -> Set[str]:
    window_end = now + timedelta(hours=recovery_window_hours)
    return {
        task.task_id
        for task in tasks
        if task.status in {TaskStatus.PENDING, TaskStatus.SCHEDULED}
        and (task.earliest_start or now) <= window_end
        and task.deadline >= now
    }


def relax_recovery_dependencies(task: Task, affected_ids: Set[str], missed_task_id: str) -> Task:
    return replace(
        task,
        dependencies=tuple(
            dep for dep in task.dependencies if dep != missed_task_id and dep in affected_ids
        ),
        status=TaskStatus.PENDING,
    )
