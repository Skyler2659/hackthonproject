from __future__ import annotations

from dataclasses import replace
from typing import Iterable, List, Set

from core.models import Task, TaskStatus


def prepare_schedulable_tasks(
    tasks: Iterable[Task],
    *,
    include_missed: bool = False,
) -> List[Task]:
    """Pending tasks with resolved dependencies; optionally include missed for late recovery."""
    task_list = list(tasks)
    resolved_ids = resolved_dependency_ids(task_list)
    allowed_statuses = {TaskStatus.PENDING}
    if include_missed:
        allowed_statuses.add(TaskStatus.MISSED)
    return [
        remove_resolved_dependencies(task, resolved_ids)
        for task in task_list
        if task.status in allowed_statuses
    ]


def resolved_dependency_ids(tasks: Iterable[Task]) -> Set[str]:
    return {
        task.task_id
        for task in tasks
        if task.status in {TaskStatus.DONE, TaskStatus.MISSED, TaskStatus.CANCELLED}
    }


def remove_resolved_dependencies(task: Task, resolved_ids: Set[str]) -> Task:
    return replace(
        task,
        dependencies=tuple(dep for dep in task.dependencies if dep not in resolved_ids),
    )
