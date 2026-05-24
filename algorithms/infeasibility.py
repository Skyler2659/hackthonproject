from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Iterable, List, Set

from algorithms.candidate_slots import default_horizon
from core.models import Task, TaskScore, UserProfile


@dataclass(frozen=True)
class InfeasibilityReason:
    code: str
    task_id: str | None
    message: str
    suggestion: str


class InfeasibilityHandler:
    """Fast preflight checks and user-facing reason codes."""

    def preflight(
        self,
        tasks: Iterable[Task],
        scores: Dict[str, TaskScore],
        profile: UserProfile,
        now: datetime,
    ) -> List[InfeasibilityReason]:
        task_list = list(tasks)
        horizon = default_horizon(task_list, now)
        reasons: List[InfeasibilityReason] = []

        if total_duration(task_list) > available_minutes(profile, now, horizon):
            reasons.append(
                InfeasibilityReason(
                    code="INSUFFICIENT_TIME",
                    task_id=None,
                    message="total task duration exceeds available windows",
                    suggestion="reduce task load or extend available windows",
                )
            )

        reasons.extend(task_environment_reasons(task_list))
        reasons.extend(task_quietness_reasons(task_list, scores))
        if has_dependency_cycle(task_list):
            reasons.append(
                InfeasibilityReason(
                    code="DEPENDENCY_CYCLE",
                    task_id=None,
                    message="task dependencies contain a cycle",
                    suggestion="check dependencies before scheduling",
                )
            )
        return reasons


def total_duration(tasks: Iterable[Task]) -> int:
    return sum(task.duration_min for task in tasks)


def available_minutes(profile: UserProfile, now: datetime, horizon: datetime) -> int:
    total = 0
    cursor = now.date()
    while cursor <= horizon.date():
        for window_start, window_end in profile.available_windows:
            start = datetime.combine(cursor, window_start)
            end = datetime.combine(cursor, window_end)
            start = max(start, now)
            end = min(end, horizon)
            if end > start:
                total += int((end - start).total_seconds() // 60)
        cursor += timedelta(days=1)
    return total


def task_environment_reasons(tasks: Iterable[Task]) -> List[InfeasibilityReason]:
  # Profile preferred environments are soft; only flag impossible task env tags.
    return []


def task_quietness_reasons(
    tasks: Iterable[Task],
    scores: Dict[str, TaskScore],
) -> List[InfeasibilityReason]:
    from algorithms.scheduling_policy import HARD_QUIETNESS_THRESHOLD

    reasons: List[InfeasibilityReason] = []
    for task in tasks:
        if task.required_quietness < HARD_QUIETNESS_THRESHOLD:
            continue
        reasons.append(
            InfeasibilityReason(
                code="QUIETNESS_TOO_HIGH",
                task_id=task.task_id,
                message="task requires extreme quietness; may be hard to schedule",
                suggestion="lower required_quietness or schedule in a known quiet block",
            )
        )
    return reasons


def has_dependency_cycle(tasks: Iterable[Task]) -> bool:
    by_id = {task.task_id: task for task in tasks}
    visiting: Set[str] = set()
    visited: Set[str] = set()

    def visit(task_id: str) -> bool:
        if task_id in visited:
            return False
        if task_id in visiting:
            return True
        visiting.add(task_id)
        for dep_id in by_id[task_id].dependencies:
            if dep_id in by_id and visit(dep_id):
                return True
        visiting.remove(task_id)
        visited.add(task_id)
        return False

    return any(visit(task.task_id) for task in tasks)
