from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List

from agents import LocalSeriesAgent, ScoringAgent
from algorithms import WeightedScheduler
from algorithms.recovery import RecoveryEngine
from algorithms.schedule_refiner import refine_schedule
from chrona_service.config import ChronaConfig
from chrona_service.exceptions import ChronaServiceError
from chrona_service.llm import build_llm_client
from chrona_service.profile import build_profile_soft_hints, build_user_profile
from chrona_service.serializers import serialize_profile, serialize_schedule_result, serialize_scores
from chrona_service.store import append_operation, load_archive, load_profile_memory, save_archive
from chrona_service.tasks import active_schedulable_tasks, materialize_tasks, task_status_value
from models import ScheduleResult, Task, TaskScore


def read_status(config: ChronaConfig, *, include_web: Dict[str, Any] | None = None) -> Dict[str, Any]:
    archive = load_archive(config.root, config.user)
    pending_tasks = list(archive.get("pending_tasks") or [])
    last_result = archive.get("last_result") if isinstance(archive.get("last_result"), dict) else None
    blocks = list((last_result or {}).get("blocks") or [])
    today = date.today()
    today_blocks = [
        block
        for block in blocks
        if str(block.get("start", "")).startswith(today.isoformat())
    ]
    result = {
        "user": config.user,
        "root": str(config.root),
        "pending_count": count_by_status(pending_tasks, "pending"),
        "unfinished_count": sum(1 for task in pending_tasks if task_status_value(task) not in {"done", "cancelled"}),
        "done_count": count_by_status(pending_tasks, "done"),
        "missed_count": count_by_status(pending_tasks, "missed"),
        "last_run_at": archive.get("last_run_at"),
        "scheduled_count": len(blocks),
        "unscheduled_task_ids": list((last_result or {}).get("unscheduled_task_ids") or []),
        "today_blocks": today_blocks,
    }
    if include_web is not None:
        result["web"] = include_web
    return result


def run_schedule(config: ChronaConfig, *, ensemble_size: int = 3) -> Dict[str, Any]:
    archive = load_archive(config.root, config.user)
    memory = load_profile_memory(config.root, config.user)
    now = datetime.now().replace(second=0, microsecond=0)
    tasks = active_schedulable_tasks(materialize_tasks(archive.get("pending_tasks") or []))
    profile = build_user_profile(memory, user_id=config.user, generous=True)
    soft_hints = build_profile_soft_hints(memory)

    if not tasks:
        result = ScheduleResult(blocks=[], unscheduled_task_ids=[], total_cost=0.0)
        archive["last_scores"] = None
        archive["last_result"] = serialize_schedule_result(result)
        archive["last_profile"] = serialize_profile(profile)
        archive["last_run_at"] = now.isoformat()
        append_operation(archive, "schedule_updated", detail="scheduled=0, unscheduled=0")
        save_archive(config.root, config.user, archive)
        return {"scores": None, "ordered_task_ids": [], "result": archive["last_result"], "refinement_summary": ""}

    llm_client = build_llm_client(config)
    scores = score_tasks(tasks, profile, soft_hints, now, llm_client, ensemble_size)
    ordered_tasks = LocalSeriesAgent().order_tasks(tasks, scores, profile)
    result = WeightedScheduler().schedule(ordered_tasks, scores, profile, now)
    result, refinement_summary = refine_schedule(
        result=result,
        tasks=tasks,
        scores=scores,
        profile=profile,
        profile_soft_hints=soft_hints,
        now=now,
        llm_client=llm_client,
    )

    archive["last_scores"] = serialize_scores(scores)
    archive["last_result"] = serialize_schedule_result(result)
    archive["last_profile"] = serialize_profile(profile)
    archive["last_run_at"] = now.isoformat()
    append_operation(
        archive,
        "schedule_updated",
        detail=f"scheduled={len(result.blocks)}, unscheduled={len(result.unscheduled_task_ids)}",
    )
    save_archive(config.root, config.user, archive)
    return {
        "scores": archive["last_scores"],
        "ordered_task_ids": [task.task_id for task in ordered_tasks],
        "result": archive["last_result"],
        "refinement_summary": refinement_summary,
    }


def recover_schedule(
    config: ChronaConfig,
    *,
    missed_task_id: str,
    ensemble_size: int = 3,
) -> Dict[str, Any]:
    archive = load_archive(config.root, config.user)
    raw_tasks = list(archive.get("pending_tasks") or [])
    target = next((task for task in raw_tasks if str(task.get("task_id")) == missed_task_id), None)
    if target is None:
        raise ChronaServiceError(f"Task not found: {missed_task_id}")

    # Preflight live LLM before mutating the archive; offline mode uses the mock client.
    pending_after_miss = [
        task
        for task in raw_tasks
        if str(task.get("task_id")) != missed_task_id and task_status_value(task) == "pending"
    ]
    if pending_after_miss:
        build_llm_client(config)

    now = datetime.now().replace(second=0, microsecond=0)
    previous_status = task_status_value(target)
    target["status"] = "missed"
    target["deadline_overdue"] = True
    all_tasks = materialize_tasks(raw_tasks)
    affected_ids = sorted(RecoveryEngine().affected_task_ids(missed_task_id, all_tasks, now))
    append_operation(
        archive,
        "task_missed",
        task_id=missed_task_id,
        title=str(target.get("title", "")),
        detail=f"recover requested; {previous_status}->missed",
    )
    save_archive(config.root, config.user, archive)
    scheduled = run_schedule(config, ensemble_size=ensemble_size)
    return {
        "missed_task_id": missed_task_id,
        "affected_task_ids": affected_ids,
        "schedule": scheduled,
    }


def score_tasks(
    tasks: List[Task],
    profile,
    soft_hints: str,
    now: datetime,
    llm_client,
    ensemble_size: int,
) -> Dict[str, TaskScore]:
    scorer = ScoringAgent(
        llm_client=llm_client,
        ensemble_size=ensemble_size,
        profile_soft_hints=soft_hints,
    )
    return {task.task_id: scorer.score_task(task, profile, now) for task in tasks}


def count_by_status(tasks: List[Dict[str, Any]], status: str) -> int:
    return sum(1 for task in tasks if task_status_value(task) == status)
