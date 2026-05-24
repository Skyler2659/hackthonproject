from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Iterable, List, Set

from algorithms.candidate_slots import default_horizon
from algorithms.constants import QUIETNESS_MARGIN
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

        reasons.extend(environment_reasons(task_list, profile))
        reasons.extend(quietness_reasons(task_list, scores, profile, now, horizon))
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


def environment_reasons(tasks: Iterable[Task], profile: UserProfile) -> List[InfeasibilityReason]:
    available = set(profile.preferred_environments)
    return [
        InfeasibilityReason(
            code="ENVIRONMENT_MISMATCH",
            task_id=task.task_id,
            message="required environment is not available in profile",
            suggestion="change the task environment or add it to preferred environments",
        )
        for task in tasks
        if not set(task.required_environment).issubset(available)
    ]


def quietness_reasons(
    tasks: Iterable[Task],
    scores: Dict[str, TaskScore],
    profile: UserProfile,
    now: datetime,
    horizon: datetime,
) -> List[InfeasibilityReason]:
    max_quietness = max_quietness_in_windows(profile, now, horizon)
    reasons: List[InfeasibilityReason] = []
    for task in tasks:
        score = scores.get(task.task_id)
        if score is None:
            continue
        required = max(task.required_quietness, score.quietness_need * 0.75)
        if required > max_quietness + QUIETNESS_MARGIN:
            reasons.append(
                InfeasibilityReason(
                    code="QUIETNESS_TOO_HIGH",
                    task_id=task.task_id,
                    message="quietness requirement is higher than any available slot",
                    suggestion="adjust quiet windows or lower quietness requirement",
                )
            )
    return reasons


def max_quietness_in_windows(profile: UserProfile, now: datetime, horizon: datetime) -> float:
    max_quietness = 0.0
    cursor = now
    while cursor <= horizon:
        max_quietness = max(max_quietness, profile.quietness_at(cursor))
        cursor += timedelta(hours=1)
    return max_quietness


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
