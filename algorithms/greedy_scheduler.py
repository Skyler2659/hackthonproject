from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Iterable, List, Set, Tuple

from algorithms.base import BaseScheduler
from core.models import ScheduleBlock, ScheduleResult, Task, TaskScore, TaskStatus, UserProfile


ENVIRONMENT_LABELS = {
    "desk": "书桌",
    "library": "图书馆",
    "classroom": "教室",
    "meeting_room": "会议室",
    "mobile": "移动场景",
    "online": "线上环境",
}


@dataclass(frozen=True)
class Slot:
    start: datetime
    end: datetime
    energy: float
    quietness: float
    environments: Tuple[str, ...]


class GreedyScheduler(BaseScheduler):
    """Deterministic MVP scheduler; CP-SAT can implement BaseScheduler later."""

    def schedule(
        self,
        tasks: Iterable[Task],
        scores: Dict[str, TaskScore],
        profile: UserProfile,
        now: datetime,
    ) -> ScheduleResult:
        active_tasks = [task for task in tasks if task.status == TaskStatus.PENDING]
        return place_tasks(priority_order(active_tasks, scores, profile), scores, profile, now)

    def recover_after_miss(
        self,
        missed_task_id: str,
        tasks: List[Task],
        scores: Dict[str, TaskScore],
        profile: UserProfile,
        now: datetime,
    ) -> ScheduleResult:
        affected_ids = affected_task_ids(missed_task_id, tasks, now)
        recovery_tasks = [
            relax_recovery_dependencies(task, affected_ids, missed_task_id)
            for task in tasks
            if task.task_id in affected_ids and task.task_id != missed_task_id
            and task.status in {TaskStatus.PENDING, TaskStatus.SCHEDULED}
        ]
        return self.schedule(recovery_tasks, scores, profile, now)


def place_tasks(
    ordered_tasks: List[Task],
    scores: Dict[str, TaskScore],
    profile: UserProfile,
    now: datetime,
) -> ScheduleResult:
    placed: List[ScheduleBlock] = []
    scheduled_ids: Set[str] = set()
    active_ids = {task.task_id for task in ordered_tasks}
    unscheduled: List[str] = []
    pending = list(ordered_tasks)

    while pending:
        next_pending, progressed = place_ready_tasks(
            pending, active_ids, scheduled_ids, placed, unscheduled, scores, profile, now
        )
        if not progressed and next_pending:
            unscheduled.extend(task.task_id for task in next_pending)
            break
        pending = next_pending

    placed.sort(key=lambda block: block.start)
    return ScheduleResult(
        blocks=placed,
        unscheduled_task_ids=sorted(set(unscheduled)),
        total_cost=total_cost(placed, scores, profile),
    )


def place_ready_tasks(
    pending: List[Task],
    active_ids: Set[str],
    scheduled_ids: Set[str],
    placed: List[ScheduleBlock],
    unscheduled: List[str],
    scores: Dict[str, TaskScore],
    profile: UserProfile,
    now: datetime,
) -> tuple[List[Task], bool]:
    deferred: List[Task] = []
    progressed = False
    for task in pending:
        if has_missing_dependency(task, active_ids, scheduled_ids):
            unscheduled.append(task.task_id)
            continue
        if not set(task.dependencies).issubset(scheduled_ids):
            deferred.append(task)
            continue
        progressed |= try_place_task(task, placed, scheduled_ids, unscheduled, scores, profile, now)
    return deferred, progressed


def try_place_task(
    task: Task,
    placed: List[ScheduleBlock],
    scheduled_ids: Set[str],
    unscheduled: List[str],
    scores: Dict[str, TaskScore],
    profile: UserProfile,
    now: datetime,
) -> bool:
    score = scores[task.task_id]
    slot = find_first_slot(task, score, profile, now, placed)
    if slot is None:
        unscheduled.append(task.task_id)
        return False

    placed.append(build_block(task, score, profile, slot))
    scheduled_ids.add(task.task_id)
    return True


def priority_order(
    tasks: List[Task],
    scores: Dict[str, TaskScore],
    profile: UserProfile,
) -> List[Task]:
    return sorted(
        tasks,
        key=lambda task: (
            -scores[task.task_id].priority(profile.weights),
            task.deadline,
            -scores[task.task_id].block_integrity,
        ),
    )


def find_first_slot(
    task: Task,
    score: TaskScore,
    profile: UserProfile,
    now: datetime,
    placed: List[ScheduleBlock],
) -> Slot | None:
    cursor = ceil_to_step(task.earliest_start or now, step_min=15)
    horizon = max(task.deadline + timedelta(hours=8), now + timedelta(days=3))
    best_slot: Slot | None = None
    best_cost: tuple[float, datetime] | None = None

    while cursor < horizon:
        candidate = build_slot(cursor, task.duration_min, profile)
        if is_available(candidate.start, candidate.end, profile) and fits(task, score, candidate, placed):
            candidate_cost = (slot_cost(task, score, profile, candidate), candidate.start)
            if best_cost is None or candidate_cost < best_cost:
                best_slot = candidate
                best_cost = candidate_cost
        cursor += timedelta(minutes=15)
    return best_slot


def build_slot(start: datetime, duration_min: int, profile: UserProfile) -> Slot:
    return Slot(
        start=start,
        end=start + timedelta(minutes=duration_min),
        energy=profile.energy_at(start),
        quietness=profile.quietness_at(start),
        environments=profile.preferred_environments,
    )


def fits(
    task: Task,
    score: TaskScore,
    slot: Slot,
    placed: List[ScheduleBlock],
) -> bool:
    if any(overlaps(slot.start, slot.end, block.start, block.end) for block in placed):
        return False
    if not set(task.required_environment).issubset(set(slot.environments)):
        return False
    quietness_need = max(task.required_quietness, score.quietness_need * 0.75)
    return slot.quietness + 0.05 >= quietness_need


def slot_cost(task: Task, score: TaskScore, profile: UserProfile, slot: Slot) -> float:
    lateness_hours = max(0.0, (slot.end - task.deadline).total_seconds() / 3600)
    cognitive_gap = abs(score.cognitive_load - slot.energy)
    quiet_gap = max(0.0, max(task.required_quietness, score.quietness_need) - slot.quietness)
    preference_fit = 1.0 - min(1.0, cognitive_gap + quiet_gap)
    priority_bonus = score.priority(profile.weights) * preference_fit
    return (
        profile.weights.lateness * lateness_hours
        + profile.weights.cognitive_fit * cognitive_gap
        + profile.weights.preference_match * quiet_gap
        - priority_bonus
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


def build_block(
    task: Task,
    score: TaskScore,
    profile: UserProfile,
    slot: Slot,
) -> ScheduleBlock:
    return ScheduleBlock(
        task_id=task.task_id,
        title=task.title,
        start=slot.start,
        end=slot.end,
        priority=score.priority(profile.weights),
        reason=reason(task, score, slot),
    )


def reason(task: Task, score: TaskScore, slot: Slot) -> str:
    return (
        f"优先级因子={score.urgency:.2f}/{score.cognitive_load:.2f}, "
        f"精力匹配={slot.energy:.2f}, 安静度={slot.quietness:.2f}, "
        f"环境={environment_text(slot.environments)}, "
        f"DDL={task.deadline:%m-%d %H:%M}"
    )


def environment_text(environments: Tuple[str, ...]) -> str:
    return ",".join(ENVIRONMENT_LABELS.get(env, env) for env in environments) or "无"


def total_cost(
    blocks: List[ScheduleBlock],
    scores: Dict[str, TaskScore],
    profile: UserProfile,
) -> float:
    cost = 0.0
    for block in blocks:
        score = scores[block.task_id]
        cognitive_gap = abs(score.cognitive_load - profile.energy_at(block.start))
        quiet_gap = max(0.0, score.quietness_need - profile.quietness_at(block.start))
        cost += cognitive_gap * profile.weights.cognitive_fit + quiet_gap
    return round(cost, 4)


def affected_task_ids(missed_task_id: str, tasks: List[Task], now: datetime | None = None) -> Set[str]:
    by_id = {task.task_id: task for task in tasks}
    affected = {missed_task_id}
    series_id = by_id[missed_task_id].series_id if missed_task_id in by_id else None

    changed = True
    while changed:
        changed = extend_affected_tasks(affected, series_id, tasks)
    if now is not None:
        affected.update(tasks_in_recovery_window(tasks, now))
    return affected


def tasks_in_recovery_window(tasks: List[Task], now: datetime) -> Set[str]:
    window_end = now + timedelta(hours=8)
    return {
        task.task_id
        for task in tasks
        if task.status in {TaskStatus.PENDING, TaskStatus.SCHEDULED}
        and (task.earliest_start or now) <= window_end
        and task.deadline >= now
    }


def extend_affected_tasks(affected: Set[str], series_id: str | None, tasks: List[Task]) -> bool:
    changed = False
    for task in tasks:
        depends_on_affected = bool(set(task.dependencies) & affected)
        same_series = bool(series_id and task.series_id == series_id)
        if (depends_on_affected or same_series) and task.task_id not in affected:
            affected.add(task.task_id)
            changed = True
    return changed


def relax_recovery_dependencies(task: Task, affected_ids: Set[str], missed_task_id: str) -> Task:
    return Task(
        task_id=task.task_id,
        title=task.title,
        description=task.description,
        duration_min=task.duration_min,
        deadline=task.deadline,
        earliest_start=task.earliest_start,
        series_id=task.series_id,
        required_environment=task.required_environment,
        required_quietness=task.required_quietness,
        dependencies=tuple(
            dep for dep in task.dependencies if dep != missed_task_id and dep in affected_ids
        ),
        must_be_contiguous=task.must_be_contiguous,
        status=TaskStatus.PENDING,
        tags=task.tags,
    )


def has_missing_dependency(task: Task, active_ids: Set[str], scheduled_ids: Set[str]) -> bool:
    return bool(set(task.dependencies) - active_ids - scheduled_ids)


def overlaps(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    return max(a_start, b_start) < min(a_end, b_end)


def ceil_to_step(moment: datetime, step_min: int) -> datetime:
    minute = ((moment.minute + step_min - 1) // step_min) * step_min
    base = moment.replace(second=0, microsecond=0, minute=0)
    return base + timedelta(minutes=minute)


WeightedScheduler = GreedyScheduler
