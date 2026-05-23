from __future__ import annotations

import html
from typing import Any, Dict, Optional

import streamlit as st

from models import ScheduleResult, Task, TaskScore, TaskStatus, UserProfile, clamp01
from web_ui.task_data import materialize_tasks, task_status_value


DIMENSION_LABELS = {
    "cognitive_load": "认知负荷",
    "urgency": "紧急度",
    "confidence": "置信度",
}


def render_results() -> None:
    result = st.session_state.last_result
    scores = st.session_state.last_scores
    profile = st.session_state.last_profile
    if result is None or scores is None or profile is None:
        return

    st.subheader("调度结果")
    render_schedule_metrics(result)
    render_unscheduled_warning(result)
    render_schedule_timeline(result, scores, task_lookup(), profile)


def render_schedule_metrics(result: ScheduleResult) -> None:
    metric_cols = st.columns(5)
    metric_cols[0].metric("已排程任务", scheduled_count(result))
    metric_cols[1].metric("未排入任务", unscheduled_count(result))
    metric_cols[2].metric("已完成任务", completed_count())
    metric_cols[3].metric("总成本", f"{result.total_cost:.4f}")
    metric_cols[4].metric("平均优先级", f"{average_priority(result):.2f}")


def scheduled_count(result: ScheduleResult) -> int:
    return len(result.blocks)


def unscheduled_count(result: ScheduleResult) -> int:
    return len(result.unscheduled_task_ids)


def completed_count() -> int:
    return sum(
        1
        for task in st.session_state.pending_tasks
        if task_status_value(task) == TaskStatus.DONE.value
    )


def average_priority(result: ScheduleResult) -> float:
    if not result.blocks:
        return 0.0
    return sum(block.priority for block in result.blocks) / len(result.blocks)


def render_unscheduled_warning(result: ScheduleResult) -> None:
    if result.unscheduled_task_ids:
        st.warning(f"未能排入窗口的任务：{', '.join(result.unscheduled_task_ids)}")


def task_lookup() -> Dict[str, Task]:
    return {
        task.task_id: task
        for task in materialize_tasks(st.session_state.pending_tasks)
    }


def render_schedule_timeline(
    result: ScheduleResult,
    scores: Dict[str, TaskScore],
    tasks: Dict[str, Task],
    profile: UserProfile,
) -> None:
    if not result.blocks:
        st.info("当前没有成功排入日程的任务。")
        return

    st.markdown('<div class="timeline-shell">', unsafe_allow_html=True)
    for index, block in enumerate(result.blocks, start=1):
        render_schedule_block(index, block, scores[block.task_id], tasks.get(block.task_id), profile)
    st.markdown("</div>", unsafe_allow_html=True)


def render_schedule_block(
    index: int,
    block: Any,
    score: TaskScore,
    task: Optional[Task],
    profile: UserProfile,
) -> None:
    priority = score.priority(profile.weights)
    st.markdown(
        schedule_block_html(index, block, score, task, priority),
        unsafe_allow_html=True,
    )


def schedule_block_html(
    index: int,
    block: Any,
    score: TaskScore,
    task: Optional[Task],
    priority: float,
) -> str:
    return f"""
    <div class="schedule-block" style="border-left-color:{priority_color(priority)};">
      <div class="schedule-head">
        <div>
          <div class="schedule-time">{block.start:%m-%d %H:%M} - {block.end:%H:%M} · {duration_min(block)} 分钟</div>
          <div class="schedule-title">{index}. {safe(block.title)}</div>
        </div>
        <div class="priority-badge" style="background:{priority_color(priority)};">优先级 {priority:.2f}</div>
      </div>
      <div class="schedule-meta">
        <span>系列：{safe(series_text(task))}</span>
        <span>依赖：{safe(dependencies_text(task))}</span>
        <span>DDL: {safe(deadline_text(task))}</span>
      </div>
      <div class="dimension-grid">
        {dimension_bar(DIMENSION_LABELS["cognitive_load"], score.cognitive_load, "#ef4444")}
        {dimension_bar(DIMENSION_LABELS["urgency"], score.urgency, "#f59e0b")}
        {dimension_bar(DIMENSION_LABELS["confidence"], score.confidence, "#2563eb")}
      </div>
      <div class="reason">{safe(block.reason)}</div>
    </div>
    """


def duration_min(block: Any) -> int:
    return int((block.end - block.start).total_seconds() / 60)


def series_text(task: Optional[Task]) -> str:
    if task and task.series_id:
        return task.series_id
    return "单独任务"


def dependencies_text(task: Optional[Task]) -> str:
    if task and task.dependencies:
        return ", ".join(task.dependencies)
    return "无"


def deadline_text(task: Optional[Task]) -> str:
    if task:
        return task.deadline.strftime("%m-%d %H:%M")
    return "未知"


def dimension_bar(label: str, value: float, color: str) -> str:
    width = int(value * 100)
    return f"""
    <div>
      <div class="dimension-label">{label} · {value:.2f}</div>
      <div class="bar"><span style="width:{width}%; background:{color};"></span></div>
    </div>
    """


def priority_color(priority: float) -> str:
    normalized = clamp01(priority / 6.0)
    if normalized >= 0.72:
        return "#dc2626"
    if normalized >= 0.52:
        return "#d97706"
    if normalized >= 0.34:
        return "#2563eb"
    return "#059669"


def safe(value: Any) -> str:
    return html.escape(str(value))
