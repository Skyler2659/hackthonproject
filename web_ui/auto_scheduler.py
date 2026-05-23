from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Tuple

import streamlit as st

from agents import LocalSeriesAgent, ScoringAgent
from algorithms import WeightedScheduler
from llm_client import DeepSeekLLMClient, LLMProviderError
from models import ScheduleResult, Task, TaskScore, UserProfile
from web_ui.profile import build_profile
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
    if not profile_config["available_windows"]:
        st.warning("请至少配置一个有效的可用时间窗，系统才能自动排程。")
        return False
    return True


def run_auto_scheduler(profile_config: Dict[str, Any]) -> None:
    try:
        tasks = active_schedulable_tasks(materialize_tasks(st.session_state.pending_tasks))
        if stop_when_no_active_tasks(tasks):
            return
        profile = build_profile(profile_config)
        st.info("任务列表已更新，正在自动生成新的时间安排。")
        scores, ordered_tasks, result = run_scheduler_pipeline(tasks, profile, profile_config)
    except LLMProviderError as exc:
        st.error(f"AI 调度失败：{exc}")
        return
    except ValueError as exc:
        st.error(f"调度输入不合法：{exc}")
        return
    except Exception as exc:  # pragma: no cover - UI safety net
        st.error(f"调度引擎执行失败：{type(exc).__name__}: {exc}")
        return

    save_schedule_result(scores, ordered_tasks, result, profile)
    st.success("日程已自动更新。")


def stop_when_no_active_tasks(tasks: List[Task]) -> bool:
    if tasks:
        return False
    st.session_state.auto_schedule_needed = False
    return True


def run_scheduler_pipeline(
    tasks: List[Task],
    profile: UserProfile,
    profile_config: Dict[str, Any],
) -> Tuple[Dict[str, TaskScore], List[Task], ScheduleResult]:
    now = datetime.now().replace(second=0, microsecond=0)
    progress = st.progress(0)
    status = st.empty()
    scores = score_tasks(tasks, profile, profile_config, now, progress, status)
    ordered_tasks = order_tasks(tasks, scores, profile, progress, status)
    result = schedule_tasks(ordered_tasks, scores, profile, now, progress, status)
    return scores, ordered_tasks, result


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
    status.write("正在生成合适的时间安排...")
    result = WeightedScheduler().schedule(ordered_tasks, scores, profile, now)
    progress.progress(100)
    status.empty()
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
) -> None:
    st.session_state.last_scores = scores
    st.session_state.last_ordered_tasks = ordered_tasks
    st.session_state.last_result = result
    st.session_state.last_profile = profile
    st.session_state.last_run_at = datetime.now().replace(second=0, microsecond=0)
    st.session_state.auto_schedule_needed = False

