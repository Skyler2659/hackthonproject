from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Tuple

import streamlit as st

from agents import LocalSeriesAgent, ScoringAgent
from algorithms import WeightedScheduler
from algorithms.force_placer import force_place_into_schedule, merge_force_join_result
from algorithms.schedule_refiner import refine_schedule
from llm_client import DeepSeekLLMClient, LLMProviderError
from models import ScheduleResult, Task, TaskScore, UserProfile
from web_ui.archive import record_operation
from web_ui.profile_soft import build_algorithm_profile, build_profile_soft_hints
from web_ui.task_data import active_schedulable_tasks, materialize_tasks


def render_auto_scheduler(profile_config: Dict[str, Any]) -> None:
    if not should_auto_schedule():
        return
    if stop_when_task_list_empty():
        return
    if not can_auto_schedule(profile_config):
        return
    run_auto_scheduler(profile_config)


def should_auto_schedule() -> bool:
    return bool(st.session_state.auto_schedule_needed)


def stop_when_task_list_empty() -> bool:
    if st.session_state.pending_tasks:
        return False
    st.session_state.auto_schedule_needed = False
    return True


def can_auto_schedule(profile_config: Dict[str, Any]) -> bool:
    if not profile_config["api_key"]:
        st.info("输入 API Key 后，日程会在任务变化时自动更新。")
        return False
    return True


def run_auto_scheduler(profile_config: Dict[str, Any]) -> None:
    try:
        tasks = active_schedulable_tasks(materialize_tasks(st.session_state.pending_tasks))
        if stop_when_no_active_tasks(tasks):
            return
        algo_profile = build_algorithm_profile(profile_config)
        soft_hints = build_profile_soft_hints(st.session_state.get("profile_memory", {}))
        profile_config = {**profile_config, "profile_soft_hints": soft_hints}

        force_ids = pop_force_join_task_ids()
        if force_ids and try_force_join_existing_schedule(tasks, force_ids, algo_profile, profile_config):
            return

        st.info("任务列表已更新，正在自动生成新的时间安排。")
        scores, ordered_tasks, result, refinement_summary = run_scheduler_pipeline(
            tasks,
            algo_profile,
            profile_config,
            force_relaxed_task_ids=force_ids,
        )
    except LLMProviderError as exc:
        st.error(f"AI 调度失败：{exc}")
        return
    except ValueError as exc:
        st.error(f"调度输入不合法：{exc}")
        return
    except Exception as exc:  # pragma: no cover - UI safety net
        st.error(f"调度引擎执行失败：{type(exc).__name__}: {exc}")
        return

    save_schedule_result(scores, ordered_tasks, result, algo_profile, refinement_summary)
    if refinement_summary:
        st.caption(refinement_summary)
    st.success("日程已自动更新。")


def stop_when_no_active_tasks(tasks: List[Task]) -> bool:
    if tasks:
        return False
    st.session_state.auto_schedule_needed = False
    return True


def try_force_join_existing_schedule(
    tasks: List[Task],
    force_ids: List[str],
    profile: UserProfile,
    profile_config: Dict[str, Any],
) -> bool:
    """Fast path: insert into current schedule without full re-solve. Returns True if handled."""
    previous = st.session_state.get("last_result")
    if previous is None:
        return False

    task_by_id = {task.task_id: task for task in tasks}
    targets = [task_by_id[task_id] for task_id in force_ids if task_id in task_by_id]
    if not targets:
        return False

    scores = dict(st.session_state.get("last_scores") or {})
    now = datetime.now().replace(second=0, microsecond=0)
    soft_hints = build_profile_soft_hints(st.session_state.get("profile_memory", {}))
    with st.spinner("AI 正在分析空档与任务间距，选择合适时段塞入..."):
        blocks, still_unscheduled = force_place_into_schedule(
            targets,
            scores,
            profile,
            now,
            list(previous.blocks),
            llm_client=build_llm_client(profile_config),
            profile_soft_hints=soft_hints,
        )
    placed_ids = {task.task_id for task in targets} - set(still_unscheduled)
    result = merge_force_join_result(previous, blocks, set(force_ids), still_unscheduled)
    summary = _force_join_summary(placed_ids, still_unscheduled, targets)
    save_schedule_result(scores, st.session_state.get("last_ordered_tasks") or targets, result, profile, summary)
    if still_unscheduled:
        st.warning(summary)
    else:
        st.success(summary)
    return True


def _force_join_summary(placed_ids: set[str], still_unscheduled: List[str], targets: List[Task]) -> str:
    titles = {task.task_id: task.title for task in targets}
    if not still_unscheduled:
        names = "、".join(titles[tid] for tid in placed_ids if tid in titles)
        return f"已智能加入日程：{names or '所选任务'}（保留任务间距，不考虑专注/深度预算）。"
    failed = "、".join(titles.get(tid, tid) for tid in still_unscheduled)
    return f"以下任务在截止前仍无空档可塞入：{failed}。可尝试放宽截止日、缩短时长或手动调整已有日程。"


def run_scheduler_pipeline(
    tasks: List[Task],
    profile: UserProfile,
    profile_config: Dict[str, Any],
    force_relaxed_task_ids: List[str] | None = None,
) -> Tuple[Dict[str, TaskScore], List[Task], ScheduleResult, str]:
    now = datetime.now().replace(second=0, microsecond=0)
    progress = st.progress(0)
    status = st.empty()
    scores = score_tasks(tasks, profile, profile_config, now, progress, status)
    ordered_tasks = order_tasks(tasks, scores, profile, progress, status)
    result = schedule_tasks(ordered_tasks, scores, profile, now, progress, status)
    status.write("AI 正在检查日程密度、冲突与未排任务...")
    progress.progress(92)
    relaxed = set(force_relaxed_task_ids or ())
    result, refinement_summary = refine_schedule(
        result=result,
        tasks=tasks,
        scores=scores,
        profile=profile,
        profile_soft_hints=str(profile_config.get("profile_soft_hints") or ""),
        now=now,
        llm_client=build_llm_client(profile_config),
        force_relaxed_task_ids=relaxed,
    )
    progress.progress(100)
    status.empty()
    return scores, ordered_tasks, result, refinement_summary


def score_tasks(
    tasks: List[Task],
    profile: UserProfile,
    profile_config: Dict[str, Any],
    now: datetime,
    progress: Any,
    status: Any,
) -> Dict[str, TaskScore]:
    scorer = ScoringAgent(
        llm_client=build_llm_client(profile_config),
        ensemble_size=profile_config["ensemble_size"],
        profile_soft_hints=str(profile_config.get("profile_soft_hints") or ""),
    )
    scores: Dict[str, TaskScore] = {}
    with st.spinner("AI 正在评估任务难度、紧急程度和专注需求..."):
        for index, task in enumerate(tasks, start=1):
            status.write(f"正在分析任务 {index}/{len(tasks)}：{task.title}")
            scores[task.task_id] = scorer.score_task(task, profile, now)
            progress.progress(10 + int(55 * index / len(tasks)))
    return scores


def order_tasks(
    tasks: List[Task],
    scores: Dict[str, TaskScore],
    profile: UserProfile,
    progress: Any,
    status: Any,
) -> List[Task]:
    status.write("正在整理任务依赖和先后关系...")
    ordered_tasks = LocalSeriesAgent().order_tasks(tasks, scores, profile)
    progress.progress(75)
    return ordered_tasks


def schedule_tasks(
    ordered_tasks: List[Task],
    scores: Dict[str, TaskScore],
    profile: UserProfile,
    now: datetime,
    progress: Any,
    status: Any,
) -> ScheduleResult:
    status.write("正在用约束求解器生成时间安排...")
    result = WeightedScheduler().schedule(ordered_tasks, scores, profile, now)
    progress.progress(88)
    return result


def build_llm_client(profile_config: Dict[str, Any]) -> DeepSeekLLMClient:
    return DeepSeekLLMClient(
        api_key=profile_config["api_key"],
        model=profile_config["model"],
        base_url=profile_config["base_url"],
    )


def save_schedule_result(
    scores: Dict[str, TaskScore],
    ordered_tasks: List[Task],
    result: ScheduleResult,
    profile: UserProfile,
    refinement_summary: str,
) -> None:
    st.session_state.last_scores = scores
    st.session_state.last_ordered_tasks = ordered_tasks
    st.session_state.last_result = result
    st.session_state.last_profile = profile
    st.session_state.last_refinement_summary = refinement_summary
    st.session_state.last_run_at = datetime.now().replace(second=0, microsecond=0)
    st.session_state.auto_schedule_needed = False
    record_operation(
        "schedule_updated",
        detail=f"scheduled={len(result.blocks)}, unscheduled={len(result.unscheduled_task_ids)}",
    )


def pop_force_join_task_ids() -> List[str]:
    raw = st.session_state.pop("force_join_task_ids", None)
    if not raw:
        return []
    return [str(task_id) for task_id in raw]


def request_force_join(task_ids: List[str]) -> None:
    """Force-insert tasks into free slots; does not wipe the current schedule."""
    st.session_state.force_join_task_ids = list(dict.fromkeys(str(task_id) for task_id in task_ids))
    st.session_state.auto_schedule_needed = True


def request_full_reschedule() -> None:
    """Full re-solve (task list changes, profile updates, etc.)."""
    from web_ui.session_state import mark_schedule_dirty

    mark_schedule_dirty()
    st.session_state.auto_schedule_needed = True
