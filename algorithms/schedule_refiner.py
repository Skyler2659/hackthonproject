from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Tuple

from agents.schedule_refinement_agent import ScheduleRefinementAgent
from algorithms.force_placer import force_place_into_schedule
from algorithms.greedy_scheduler import (
    build_block,
    build_slot,
    ceil_to_step,
    find_first_slot,
    slot_is_feasible,
    slot_cost,
)
from algorithms.greedy_scheduler import Slot
from algorithms.scheduling_policy import earliest_start_for_task, placed_end_times, quietness_is_hard
from algorithms.semantic_rules import blocks_have_required_buffer
from core.models import ScheduleBlock, ScheduleResult, Task, TaskScore, UserProfile
from llm_client import LLMClient


def refine_schedule(
    result: ScheduleResult,
    tasks: List[Task],
    scores: Dict[str, TaskScore],
    profile: UserProfile,
    profile_soft_hints: str,
    now: datetime,
    llm_client: LLMClient | None = None,
    force_relaxed_task_ids: set[str] | None = None,
) -> Tuple[ScheduleResult, str]:
    relaxed = force_relaxed_task_ids or set()
    """Post-solver AI review + deterministic apply. Returns updated schedule and user summary."""
    review = _load_review(result, tasks, scores, profile, profile_soft_hints, now, llm_client)
    blocks = list(result.blocks)
    unscheduled = set(result.unscheduled_task_ids)
    task_by_id = {task.task_id: task for task in tasks}

    blocks = _apply_block_adjustments(blocks, review.get("block_adjustments") or [], task_by_id, scores, profile, now)
    blocks = _resolve_conflicts(blocks, task_by_id, scores, profile, now)

    retry_ids = list(review.get("retry_unscheduled") or [])
    if not retry_ids:
        retry_ids = sorted(unscheduled)
    placed_ids = {block.task_id for block in blocks}
    placed_tasks = {block.task_id: task_by_id[block.task_id] for block in blocks if block.task_id in task_by_id}
    for task_id in retry_ids:
        if task_id in placed_ids or task_id not in task_by_id:
            continue
        task = task_by_id[task_id]
        if task_id in relaxed:
            forced_blocks, still = force_place_into_schedule(
                [task],
                scores,
                profile,
                now,
                blocks,
                llm_client=llm_client,
                profile_soft_hints=profile_soft_hints,
            )
            if task_id in still:
                block = None
            else:
                blocks = forced_blocks
                block = next(item for item in blocks if item.task_id == task_id)
        else:
            block = _try_place_unscheduled(
                task,
                scores,
                profile,
                now,
                blocks,
                placed_tasks,
                intensified=True,
            )
        if block is not None:
            blocks.append(block)
            placed_ids.add(task_id)
            placed_tasks[task_id] = task_by_id[task_id]
            unscheduled.discard(task_id)

    leave = {item.get("task_id") for item in review.get("leave_unscheduled") or [] if item.get("task_id")}
    for task_id in list(unscheduled):
        if task_id in placed_ids:
            unscheduled.discard(task_id)
    unscheduled.update(leave - placed_ids)

    blocks.sort(key=lambda block: block.start)
    summary = str(review.get("summary") or _default_summary(review, len(unscheduled)))
    return (
        ScheduleResult(
            blocks=blocks,
            unscheduled_task_ids=sorted(unscheduled),
            total_cost=result.total_cost,
        ),
        summary,
    )


def _load_review(
    result: ScheduleResult,
    tasks: List[Task],
    scores: Dict[str, TaskScore],
    profile: UserProfile,
    profile_soft_hints: str,
    now: datetime,
    llm_client: LLMClient | None,
) -> Dict[str, Any]:
    if llm_client is None:
        return _heuristic_review(result, tasks, scores, now)
    try:
        agent = ScheduleRefinementAgent(llm_client=llm_client)
        return agent.review(result, tasks, scores, profile, profile_soft_hints, now)
    except Exception:
        return _heuristic_review(result, tasks, scores, now)


def _heuristic_review(
    result: ScheduleResult,
    tasks: List[Task],
    scores: Dict[str, TaskScore],
    now: datetime,
) -> Dict[str, Any]:
    blocks = sorted(result.blocks, key=lambda item: item.start)
    density = "balanced"
    adjustments: List[Dict[str, Any]] = []
    if len(blocks) >= 2:
        gaps = [(blocks[index + 1].start - blocks[index].end).total_seconds() / 60 for index in range(len(blocks) - 1)]
        if gaps and min(gaps) < 10:
            density = "too_dense"
        elif gaps and min(gaps) > 120 and len(result.unscheduled_task_ids) == 0:
            density = "too_sparse"

    leave = [
        {"task_id": task_id, "reason": "当前时间窗内无法在截止前排入，请手动调整时长或截止日"}
        for task_id in result.unscheduled_task_ids
    ]
    return {
        "density": density,
        "block_adjustments": adjustments,
        "retry_unscheduled": list(result.unscheduled_task_ids),
        "leave_unscheduled": leave,
        "summary": _density_message(density, len(result.unscheduled_task_ids)),
    }


def _density_message(density: str, unscheduled_count: int) -> str:
    base = {
        "too_dense": "日程偏紧，已在规则层尽量拉开间隔。",
        "too_sparse": "日程偏松，可继续塞入未排任务。",
        "balanced": "整体节奏尚可。",
    }.get(density, "已完成规则检查。")
    if unscheduled_count:
        return f"{base}仍有 {unscheduled_count} 项需你手动安排或放宽条件。"
    return base


def _default_summary(review: Dict[str, Any], unscheduled_count: int) -> str:
    return _density_message(str(review.get("density") or "balanced"), unscheduled_count)


def _apply_block_adjustments(
    blocks: List[ScheduleBlock],
    adjustments: Iterable[Dict[str, Any]],
    task_by_id: Dict[str, Task],
    scores: Dict[str, TaskScore],
    profile: UserProfile,
    now: datetime,
) -> List[ScheduleBlock]:
    block_by_id = {block.task_id: block for block in blocks}
    for item in adjustments:
        task_id = str(item.get("task_id") or "")
        new_start_raw = item.get("new_start")
        if not task_id or not new_start_raw or task_id not in block_by_id:
            continue
        task = task_by_id.get(task_id)
        block = block_by_id[task_id]
        if task is None:
            continue
        try:
            new_start = datetime.fromisoformat(str(new_start_raw)).replace(second=0, microsecond=0)
        except ValueError:
            continue
        duration = block.end - block.start
        new_end = new_start + duration
        if new_start < now or new_end > task.deadline:
            continue
        candidate = replace(
            block,
            start=new_start,
            end=new_end,
            reason=f"{block.reason}；AI微调：{item.get('reason', '')}",
        )
        others = [other for other in blocks if other.task_id != task_id]
        if _block_fits(candidate, task, scores.get(task_id), profile, now, others, task_by_id):
            block_by_id[task_id] = candidate
    return list(block_by_id.values())


def _resolve_conflicts(
    blocks: List[ScheduleBlock],
    task_by_id: Dict[str, Task],
    scores: Dict[str, TaskScore],
    profile: UserProfile,
    now: datetime,
) -> List[ScheduleBlock]:
    ordered = sorted(blocks, key=lambda block: block.start)
    resolved: List[ScheduleBlock] = []
    for block in ordered:
        task = task_by_id.get(block.task_id)
        if task is None:
            continue
        if _block_fits(block, task, scores.get(task.task_id), profile, now, resolved, task_by_id):
            resolved.append(block)
    return resolved


def _block_fits(
    block: ScheduleBlock,
    task: Task,
    score: TaskScore | None,
    profile: UserProfile,
    now: datetime,
    placed: List[ScheduleBlock],
    task_by_id: Dict[str, Task],
) -> bool:
    if score is None:
        return False
    if task.manual_start is not None and block.start != task.manual_start:
        return False
    for dep_id in task.dependencies:
        dep_blocks = [item for item in placed if item.task_id == dep_id]
        if dep_blocks and block.start < max(item.end for item in dep_blocks):
            return False
    slot = Slot(
        start=block.start,
        end=block.end,
        energy=profile.energy_at(block.start),
        quietness=profile.quietness_at(block.start),
        environments=task.required_environment or profile.preferred_environments,
    )
    placed_tasks = {item.task_id: task_by_id[item.task_id] for item in placed if item.task_id in task_by_id}
    return slot_is_feasible(
        task,
        score,
        profile,
        now,
        slot,
        placed,
        placed_tasks,
        strict=quietness_is_hard(task),
    ) and all(
        blocks_have_required_buffer(left, block, task_by_id)
        for left in placed
        if left.end <= block.start
    )


def _try_place_unscheduled(
    task: Task,
    scores: Dict[str, TaskScore],
    profile: UserProfile,
    now: datetime,
    placed: List[ScheduleBlock],
    placed_tasks: Dict[str, Task],
    *,
    intensified: bool,
) -> ScheduleBlock | None:
    score = scores.get(task.task_id)
    if score is None:
        return None
    slot = find_first_slot(
        task, score, profile, now, placed, placed_tasks, strict=quietness_is_hard(task)
    )
    if slot is None:
        slot = find_first_slot(task, score, profile, now, placed, placed_tasks, strict=False)
    if slot is None and intensified:
        slot = _find_intensified_slot(task, score, profile, now, placed, placed_tasks)
    if slot is None:
        return None
    return build_block(task, score, profile, slot)


def _find_intensified_slot(
    task: Task,
    score: TaskScore,
    profile: UserProfile,
    now: datetime,
    placed: List[ScheduleBlock],
    placed_tasks: Dict[str, Task],
) -> Slot | None:
    """Walk timeline with 15-min steps, accepting soft preference violations."""
    cursor = ceil_to_step(earliest_start_for_task(task, now, placed_end_times(placed)), step_min=15)
    latest_end = task.deadline
    best: Tuple[float, Slot] | None = None
    while cursor + timedelta(minutes=task.duration_min) <= latest_end:
        candidate = build_slot(task, cursor, profile)
        if slot_is_feasible(
            task, score, profile, now, candidate, placed, placed_tasks, strict=False
        ):
            cost = slot_cost(task, score, profile, candidate)
            if best is None or cost < best[0]:
                best = (cost, candidate)
        cursor += timedelta(minutes=15)
    return best[1] if best else None
