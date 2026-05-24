from __future__ import annotations

from datetime import datetime, timedelta
from typing import Iterable, List, Tuple

from algorithms.constants import DEADLINE_GRACE_HOURS, DEFAULT_HORIZON_DAYS
from core.models import Task, TaskScore, TaskStatus, UserProfile


def allows_late_slots(task: Task, now: datetime) -> bool:
    """DDL is a hard scheduling boundary for every task."""
    return False


def latest_end_for_task(task: Task, now: datetime, horizon: datetime | None = None) -> datetime:
    """Last allowed end time for a candidate slot. Never later than DDL."""
    return task.deadline


def earliest_start_for_task(
    task: Task,
    now: datetime,
    placed_ends_by_id: dict[str, datetime] | None = None,
) -> datetime:
    """Respect earliest_start, now, and dependency finish times."""
    if task.manual_start is not None:
        earliest = task.manual_start
    else:
        earliest = max(task.earliest_start or now, now)
    if not placed_ends_by_id:
        return earliest
    for dep_id in task.dependencies:
        dep_end = placed_ends_by_id.get(dep_id)
        if dep_end is not None:
            earliest = max(earliest, dep_end)
    return earliest


def slot_environments(profile: UserProfile, task: Task) -> Tuple[str, ...]:
    """Task-required environments are always schedulable even if omitted from sidebar prefs."""
    merged = set(profile.preferred_environments) | set(task.required_environment)
    return tuple(merged or profile.preferred_environments or ("desk",))


def quietness_requirement(task: Task, score: TaskScore, *, strict: bool) -> float:
    ai_need = score.quietness_need * (0.75 if strict else 0.55)
    return max(task.required_quietness, ai_need)


def environment_fits(task: Task, environments: Tuple[str, ...]) -> bool:
    if not task.required_environment:
        return True
    return set(task.required_environment).issubset(set(environments))


def quietness_fits(
    task: Task,
    score: TaskScore,
    quietness: float,
    *,
    strict: bool,
    margin: float = 0.05,
) -> bool:
    required = quietness_requirement(task, score, strict=strict)
    return quietness + margin >= required


def placed_end_times(blocks: Iterable) -> dict[str, datetime]:
    return {block.task_id: block.end for block in blocks}
