from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

from agents.force_placement_agent import ForcePlacementAgent
from algorithms.greedy_scheduler import Slot, build_block, build_slot, ceil_to_step, has_buffer_conflict
from algorithms.scheduling_policy import earliest_start_for_task, latest_end_for_task, placed_end_times
from core.models import ScheduleBlock, ScheduleResult, Task, TaskScore, UserProfile
from llm_client import LLMClient

SLOT_STEP_MIN = 15
MAX_FORCE_CANDIDATES = 24
AGENT_CANDIDATE_LIMIT = 12


@dataclass(frozen=True)
class ForceSlotCandidate:
    slot_id: str
    start: datetime
    end: datetime
    gap_before_min: int
    gap_after_min: int
    neighbor_before: str | None
    neighbor_after: str | None
    heuristic_score: float


def force_place_into_schedule(
    tasks: List[Task],
    scores: Dict[str, TaskScore],
    profile: UserProfile,
    now: datetime,
    existing_blocks: List[ScheduleBlock],
    llm_client: LLMClient | None = None,
    profile_soft_hints: str = "",
) -> Tuple[List[ScheduleBlock], List[str]]:
    """Insert tasks: hard DDL/overlap/deps + transition gaps; no focus/deep-work/env soft rules.

    Final slot chosen by ForcePlacementAgent when LLM is available, else heuristic rank.
    """
    blocks = sorted(existing_blocks, key=lambda block: block.start)
    placed_tasks: Dict[str, Task] = _blocks_to_tasks(blocks, tasks)
    placed_ids: Set[str] = {block.task_id for block in blocks}
    still_unscheduled: List[str] = []

    pending = [task for task in tasks if task.task_id not in placed_ids]
    pending.sort(key=lambda task: (task.deadline, -task.duration_min))

    while pending:
        progressed = False
        next_round: List[Task] = []
        for task in pending:
            if not set(task.dependencies).issubset(placed_ids):
                next_round.append(task)
                continue
            score = scores.get(task.task_id) or _neutral_score(task)
            block = _place_one_force(
                task,
                score,
                profile,
                now,
                blocks,
                placed_tasks,
                llm_client=llm_client,
                profile_soft_hints=profile_soft_hints,
            )
            if block is None:
                next_round.append(task)
                continue
            blocks = [block for block in blocks if block.task_id != task.task_id]
            blocks.append(block)
            blocks.sort(key=lambda item: item.start)
            placed_tasks[task.task_id] = task
            placed_ids.add(task.task_id)
            progressed = True
        if not progressed:
            still_unscheduled.extend(task.task_id for task in next_round)
            break
        pending = next_round

    return blocks, still_unscheduled


def merge_force_join_result(
    previous: ScheduleResult,
    blocks: List[ScheduleBlock],
    force_attempted_ids: Set[str],
    still_unscheduled: List[str],
) -> ScheduleResult:
    unscheduled = set(previous.unscheduled_task_ids)
    for task_id in force_attempted_ids:
        unscheduled.discard(task_id)
    unscheduled.update(still_unscheduled)
    return ScheduleResult(
        blocks=sorted(blocks, key=lambda block: block.start),
        unscheduled_task_ids=sorted(unscheduled),
        total_cost=previous.total_cost,
    )


def _place_one_force(
    task: Task,
    score: TaskScore,
    profile: UserProfile,
    now: datetime,
    placed: List[ScheduleBlock],
    placed_tasks: Dict[str, Task],
    llm_client: LLMClient | None,
    profile_soft_hints: str,
) -> ScheduleBlock | None:
    candidates = generate_force_candidates(task, profile, now, placed, placed_tasks)
    if not candidates:
        return None
    chosen, pick_reason = choose_force_candidate(
        task,
        score,
        candidates,
        placed,
        placed_tasks,
        llm_client=llm_client,
        profile_soft_hints=profile_soft_hints,
        now=now,
    )
    if chosen is None:
        return None
    slot = Slot(
        start=chosen.start,
        end=chosen.end,
        energy=profile.energy_at(chosen.start),
        quietness=profile.quietness_at(chosen.start),
        environments=profile.preferred_environments,
    )
    block = build_block(task, score, profile, slot)
    spacing = (
        f"前距{chosen.gap_before_min}分/后距{chosen.gap_after_min}分；"
        f"邻接：{chosen.neighbor_before or '—'} → {chosen.neighbor_after or '—'}"
    )
    reason = pick_reason or f"规则优选时段（{spacing}）"
    return replace(block, reason=f"智能塞入：{reason}")


def generate_force_candidates(
    task: Task,
    profile: UserProfile,
    now: datetime,
    placed: List[ScheduleBlock],
    placed_tasks: Dict[str, Task],
) -> List[ForceSlotCandidate]:
    if task.manual_start is not None and task.manual_end is not None:
        slot = build_slot(task, task.manual_start, profile)
        if not _force_slot_ok(task, slot, now, placed, placed_tasks):
            return []
        candidate = _candidate_from_slot(task, slot, placed, placed_tasks)
        return [candidate] if candidate else []

    ends_by_id = placed_end_times(placed)
    cursor = ceil_to_step(earliest_start_for_task(task, now, ends_by_id), step_min=SLOT_STEP_MIN)
    latest_end = latest_end_for_task(task, now)
    raw: List[ForceSlotCandidate] = []

    while cursor + timedelta(minutes=task.duration_min) <= latest_end:
        slot = build_slot(task, cursor, profile)
        if _force_slot_ok(task, slot, now, placed, placed_tasks):
            candidate = _candidate_from_slot(task, slot, placed, placed_tasks)
            if candidate is not None:
                raw.append(candidate)
        cursor += timedelta(minutes=SLOT_STEP_MIN)

    if not raw:
        return []
    ranked = sorted(raw, key=lambda item: item.heuristic_score, reverse=True)
    return _diversify_candidates(ranked)


def choose_force_candidate(
    task: Task,
    score: TaskScore,
    candidates: List[ForceSlotCandidate],
    placed: List[ScheduleBlock],
    placed_tasks: Dict[str, Task],
    llm_client: LLMClient | None,
    profile_soft_hints: str,
    now: datetime,
) -> Tuple[Optional[ForceSlotCandidate], str]:
    shortlist = candidates[:AGENT_CANDIDATE_LIMIT]
    by_id = {item.slot_id: item for item in shortlist}

    if llm_client is not None:
        try:
            response = ForcePlacementAgent(llm_client=llm_client).choose_slot(
                task=task,
                score=score,
                candidates=[_candidate_payload(item) for item in shortlist],
                existing_blocks=_blocks_payload(placed, placed_tasks),
                profile_soft_hints=profile_soft_hints,
                now=now,
            )
            chosen_id = str(response.get("chosen_slot_id") or "")
            if chosen_id in by_id:
                reason = str(response.get("reason") or "").strip()
                return by_id[chosen_id], reason
        except Exception:
            pass

    if not shortlist:
        return None, ""
    return shortlist[0], ""


def _candidate_from_slot(
    task: Task,
    slot: Slot,
    placed: List[ScheduleBlock],
    placed_tasks: Dict[str, Task],
) -> ForceSlotCandidate | None:
    gap_before, neighbor_before = _gap_before(slot.start, placed, placed_tasks)
    gap_after, neighbor_after = _gap_after(slot.end, placed, placed_tasks)
    slack_min = max(0, int((task.deadline - slot.end).total_seconds() // 60))
    gap_values = [gap for gap in (gap_before, gap_after) if gap is not None]
    min_gap = min(gap_values) if gap_values else 999
    density_penalty = 2.0 if min_gap < 10 else 0.0
    margin_bonus = min(min_gap, 60) / 60.0
    slack_bonus = min(slack_min, 24 * 60) / (24 * 60) * 0.3
    score = margin_bonus + slack_bonus - density_penalty
    return ForceSlotCandidate(
        slot_id=f"slot_{slot.start:%Y%m%d%H%M}",
        start=slot.start,
        end=slot.end,
        gap_before_min=gap_before if gap_before is not None else 24 * 60,
        gap_after_min=gap_after if gap_after is not None else 24 * 60,
        neighbor_before=neighbor_before,
        neighbor_after=neighbor_after,
        heuristic_score=score,
    )


def _gap_before(
    start: datetime,
    placed: List[ScheduleBlock],
    placed_tasks: Dict[str, Task],
) -> Tuple[Optional[int], Optional[str]]:
    prior = [block for block in placed if block.end <= start]
    if not prior:
        return None, None
    block = max(prior, key=lambda item: item.end)
    minutes = int((start - block.end).total_seconds() // 60)
    other = placed_tasks.get(block.task_id)
    return minutes, other.title if other else block.title


def _gap_after(
    end: datetime,
    placed: List[ScheduleBlock],
    placed_tasks: Dict[str, Task],
) -> Tuple[Optional[int], Optional[str]]:
    following = [block for block in placed if block.start >= end]
    if not following:
        return None, None
    block = min(following, key=lambda item: item.start)
    minutes = int((block.start - end).total_seconds() // 60)
    other = placed_tasks.get(block.task_id)
    return minutes, other.title if other else block.title


def _diversify_candidates(ranked: List[ForceSlotCandidate]) -> List[ForceSlotCandidate]:
    if len(ranked) <= MAX_FORCE_CANDIDATES:
        return ranked
    picks: List[ForceSlotCandidate] = []
    seen: Set[str] = set()

    def add(item: ForceSlotCandidate) -> None:
        if item.slot_id not in seen:
            picks.append(item)
            seen.add(item.slot_id)

    add(ranked[0])
    add(ranked[-1])
    if len(ranked) > 2:
        add(ranked[len(ranked) // 2])
    stride = max(1, len(ranked) // (MAX_FORCE_CANDIDATES - len(picks)))
    for index in range(0, len(ranked), stride):
        add(ranked[index])
        if len(picks) >= MAX_FORCE_CANDIDATES:
            break
    for item in ranked:
        if len(picks) >= MAX_FORCE_CANDIDATES:
            break
        add(item)
    return picks[:MAX_FORCE_CANDIDATES]


def _candidate_payload(candidate: ForceSlotCandidate) -> Dict[str, Any]:
    return {
        "slot_id": candidate.slot_id,
        "start": candidate.start.isoformat(),
        "end": candidate.end.isoformat(),
        "gap_before_min": candidate.gap_before_min,
        "gap_after_min": candidate.gap_after_min,
        "neighbor_before": candidate.neighbor_before,
        "neighbor_after": candidate.neighbor_after,
        "heuristic_score": round(candidate.heuristic_score, 3),
    }


def _blocks_payload(
    placed: List[ScheduleBlock],
    placed_tasks: Dict[str, Task],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for block in sorted(placed, key=lambda item: item.start):
        other = placed_tasks.get(block.task_id)
        rows.append(
            {
                "task_id": block.task_id,
                "title": other.title if other else block.title,
                "start": block.start.isoformat(),
                "end": block.end.isoformat(),
            }
        )
    return rows


def _blocks_to_tasks(blocks: List[ScheduleBlock], tasks: List[Task]) -> Dict[str, Task]:
    by_id = {task.task_id: task for task in tasks}
    for block in blocks:
        by_id.setdefault(
            block.task_id,
            Task(
                task_id=block.task_id,
                title=block.title,
                description="",
                duration_min=max(5, int((block.end - block.start).total_seconds() // 60)),
                deadline=block.end,
            ),
        )
    return by_id


def _force_slot_ok(
    task: Task,
    slot: Slot,
    now: datetime,
    placed: List[ScheduleBlock],
    placed_tasks: Dict[str, Task],
) -> bool:
    if slot.start < now.replace(second=0, microsecond=0):
        return False
    if slot.end > task.deadline:
        return False
    if task.manual_start is not None and slot.start != task.manual_start:
        return False
    if task.manual_end is not None and slot.end != task.manual_end:
        return False
    for dep_id in task.dependencies:
        dep_ends = [block.end for block in placed if block.task_id == dep_id]
        if dep_ends and slot.start < max(dep_ends):
            return False
    for block in placed:
        if overlaps(slot.start, slot.end, block.start, block.end):
            return False
    return not has_buffer_conflict(task, slot, placed, placed_tasks)


def overlaps(start_a: datetime, end_a: datetime, start_b: datetime, end_b: datetime) -> bool:
    return start_a < end_b and end_a > start_b


def _neutral_score(task: Task) -> TaskScore:
    return TaskScore(
        task_id=task.task_id,
        urgency=0.5,
        complexity=0.4,
        cognitive_load=0.4,
        block_integrity=0.3,
        quietness_need=0.2,
        confidence=0.6,
        rationale="强制塞入默认分",
    ).normalized()
