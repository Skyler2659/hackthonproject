from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Iterable, List, Tuple

from algorithms.constants import (
    COST_SCALE,
    DEADLINE_GRACE_HOURS,
    DEFAULT_HORIZON_DAYS,
    MAX_CANDIDATE_SLOTS_PER_TASK,
    PREFERENCE_WINDOW_PENALTY,
    SLOT_STEP_MIN,
)
from algorithms.scheduling_policy import quietness_is_hard
from algorithms.scheduling_policy import (
    environment_fits,
    latest_end_for_task,
    quietness_fits,
    quietness_requirement,
    slot_environments,
)
from core.models import Task, TaskScore, UserProfile, clamp01


@dataclass(frozen=True)
class CandidateSlot:
    slot_id: str
    task_id: str
    start: datetime
    end: datetime
    energy: float
    quietness: float
    environments: Tuple[str, ...]
    cost_lateness: int
    cost_cognitive: int
    cost_quiet: int
    cost_priority_bonus: int
    cost_preference_window: int = 0
    feasible: bool = True


class CandidateSlotGenerator:
    """Generates bounded, pre-costed slots for CP-SAT variables."""

    def __init__(
        self,
        step_min: int = SLOT_STEP_MIN,
        max_slots_per_task: int = MAX_CANDIDATE_SLOTS_PER_TASK,
    ) -> None:
        self.step_min = step_min
        self.max_slots_per_task = max_slots_per_task

    def generate(
        self,
        tasks: Iterable[Task],
        scores: Dict[str, TaskScore],
        profile: UserProfile,
        now: datetime,
        horizon: datetime | None = None,
    ) -> Dict[str, List[CandidateSlot]]:
        task_list = list(tasks)
        horizon = horizon or default_horizon(task_list, now)
        return {
            task.task_id: self.generate_for_task(task, scores[task.task_id], profile, now, horizon)
            for task in task_list
            if task.task_id in scores
        }

    def generate_for_task(
        self,
        task: Task,
        score: TaskScore,
        profile: UserProfile,
        now: datetime,
        horizon: datetime,
    ) -> List[CandidateSlot]:
        from algorithms.scheduling_policy import earliest_start_for_task

        if task.manual_start is not None and task.manual_end is not None:
            return self._manual_slot(task, score, profile)

        cursor = ceil_to_step(earliest_start_for_task(task, now), self.step_min)
        latest_end = latest_end_for_task(task, now, horizon)
        candidates: List[CandidateSlot] = []

        while cursor + timedelta(minutes=task.duration_min) <= latest_end:
            slot = self._build_slot(task, score, profile, now, horizon, cursor)
            if slot.feasible:
                candidates.append(slot)
            cursor += timedelta(minutes=self.step_min)

        candidates.sort(key=lambda slot: (slot_sort_cost(slot, profile), slot.start))
        return candidates[: self.max_slots_per_task]

    def _build_slot(
        self,
        task: Task,
        score: TaskScore,
        profile: UserProfile,
        now: datetime,
        horizon: datetime,
        start: datetime,
    ) -> CandidateSlot:
        from algorithms.scheduling_policy import allows_late_slots

        end = start + timedelta(minutes=task.duration_min)
        energy = profile.energy_at(start)
        quietness = profile.quietness_at(start)
        environments = slot_environments(profile, task)
        if end <= task.deadline:
            deadline_ok = True
        elif allows_late_slots(task, now):
            deadline_ok = end <= latest_end_for_task(task, now, horizon)
        else:
            deadline_ok = False
        hard_quiet = quietness_is_hard(task)
        feasible = (
            deadline_ok
            and is_available(start, end, profile)
            and environment_fits(task, environments)
            and quietness_fits(task, score, quietness, strict=hard_quiet)
        )
        return CandidateSlot(
            slot_id=f"{task.task_id}@{start:%Y%m%d%H%M}",
            task_id=task.task_id,
            start=start,
            end=end,
            energy=energy,
            quietness=quietness,
            environments=environments,
            cost_lateness=scaled_lateness(end, task.deadline),
            cost_cognitive=scaled_abs(score.cognitive_load - energy),
            cost_quiet=scaled_quiet_gap(task, score, quietness),
            cost_priority_bonus=scaled_priority_bonus(task, score, profile, energy, quietness),
            cost_preference_window=preference_window_penalty(start, end, profile),
            feasible=feasible,
        )

    def _manual_slot(
        self,
        task: Task,
        score: TaskScore,
        profile: UserProfile,
    ) -> List[CandidateSlot]:
        if task.manual_start is None or task.manual_end is None:
            return []
        expected_end = task.manual_start + timedelta(minutes=task.duration_min)
        feasible = (
            task.manual_end == expected_end
            and task.manual_start < task.manual_end
            and task.manual_end <= task.deadline
        )
        energy = profile.energy_at(task.manual_start)
        quietness = profile.quietness_at(task.manual_start)
        environments = slot_environments(profile, task)
        slot = CandidateSlot(
            slot_id=f"{task.task_id}@manual_{task.manual_start:%Y%m%d%H%M}",
            task_id=task.task_id,
            start=task.manual_start,
            end=task.manual_end,
            energy=energy,
            quietness=quietness,
            environments=environments,
            cost_lateness=scaled_lateness(task.manual_end, task.deadline),
            cost_cognitive=scaled_abs(score.cognitive_load - energy),
            cost_quiet=scaled_quiet_gap(task, score, quietness),
            cost_priority_bonus=scaled_priority_bonus(task, score, profile, energy, quietness),
            feasible=feasible,
        )
        return [slot] if slot.feasible else []


def default_horizon(tasks: List[Task], now: datetime) -> datetime:
    if not tasks:
        return now + timedelta(days=DEFAULT_HORIZON_DAYS)
    latest_deadline = max(task.deadline for task in tasks)
    return max(
        latest_deadline + timedelta(hours=DEADLINE_GRACE_HOURS),
        now + timedelta(days=DEFAULT_HORIZON_DAYS),
    )


def is_available(start: datetime, end: datetime, profile: UserProfile) -> bool:
    if start.date() != end.date():
        return False
    start_t = start.time()
    end_t = end.time()
    return any(
        window_start <= start_t and end_t <= window_end
        for window_start, window_end in profile.available_windows
    )


def slot_sort_cost(slot: CandidateSlot, profile: UserProfile) -> int:
    weights = profile.weights
    return int(
        round(
            weights.lateness * slot.cost_lateness
            + weights.cognitive_fit * slot.cost_cognitive
            + weights.preference_match * slot.cost_quiet
            + slot.cost_priority_bonus
            + slot.cost_preference_window
        )
    )


def preference_window_penalty(start: datetime, end: datetime, profile: UserProfile) -> int:
    windows = profile.preferred_windows or profile.available_windows
    if not windows:
        return 0
    start_t = start.time()
    end_t = end.time()
    if start.date() == end.date() and any(
        window_start <= start_t and end_t <= window_end for window_start, window_end in windows
    ):
        return 0
    return PREFERENCE_WINDOW_PENALTY


def scaled_lateness(end: datetime, deadline: datetime) -> int:
    late_hours = max(0.0, (end - deadline).total_seconds() / 3600)
    return int(round(late_hours * COST_SCALE))


def scaled_abs(value: float) -> int:
    return int(round(abs(value) * COST_SCALE))


def scaled_quiet_gap(task: Task, score: TaskScore, quietness: float) -> int:
    required = quietness_requirement(task, score, strict=True)
    return int(round(max(0.0, required - quietness) * COST_SCALE))


def scaled_priority_bonus(
    task: Task,
    score: TaskScore,
    profile: UserProfile,
    energy: float,
    quietness: float,
) -> int:
    cognitive_gap = abs(score.cognitive_load - energy)
    quiet_gap = max(0.0, quietness_requirement(task, score, strict=True) - quietness)
    fit = clamp01(1.0 - cognitive_gap - quiet_gap)
    return -int(round(score.priority(profile.weights) * fit * COST_SCALE))


def ceil_to_step(moment: datetime, step_min: int = SLOT_STEP_MIN) -> datetime:
    minute = ((moment.minute + step_min - 1) // step_min) * step_min
    base = moment.replace(second=0, microsecond=0, minute=0)
    return base + timedelta(minutes=minute)
