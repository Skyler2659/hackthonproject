from __future__ import annotations

import html
from datetime import datetime
from typing import Any, Dict, List

import streamlit as st

from models import TaskStatus
from web_ui.archive import record_operation
from web_ui.constants import ENVIRONMENT_LABELS
from web_ui.session_state import mark_schedule_dirty
from web_ui.auto_scheduler import request_force_join
from web_ui.task_data import clear_tasks, remove_task, task_status_value
from web_ui.task_edit import start_task_edit


STATUS_LABELS = {
    TaskStatus.PENDING.value: "待排程",
    TaskStatus.SCHEDULED.value: "已排程",
    TaskStatus.MISSED.value: "已超时",
    TaskStatus.DONE.value: "已完成",
    TaskStatus.CANCELLED.value: "已取消",
}


def render_pending_tasks() -> None:
    _, center, _ = st.columns([0.35, 4.3, 0.35])
    with center:
        render_task_list_content()


def render_task_list_content() -> None:
    all_tasks = st.session_state.pending_tasks
    tasks = unresolved_tasks(all_tasks)
    st.markdown('<div class="task-list-shell">', unsafe_allow_html=True)
    st.subheader("未安排任务")

    if not tasks:
        render_empty_unresolved_list()
        st.markdown("</div>", unsafe_allow_html=True)
        return

    status_counts = count_tasks_by_status(all_tasks)
    col_left, col_right = st.columns([4, 1.2])
    with col_left:
        render_unresolved_task_cards(tasks)
    with col_right:
        render_task_list_actions(all_tasks, status_counts)
    st.markdown("</div>", unsafe_allow_html=True)


def unresolved_tasks(tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    result = st.session_state.get("last_result")
    if result is None:
        return [
            task
            for task in tasks
            if task_status_value(task) not in {TaskStatus.DONE.value, TaskStatus.CANCELLED.value}
        ]

    scheduled_ids = {block.task_id for block in result.blocks}
    unscheduled_ids = set(result.unscheduled_task_ids)
    return [
        task
        for task in tasks
        if task_status_value(task) not in {TaskStatus.DONE.value, TaskStatus.CANCELLED.value}
        and (
            str(task["task_id"]) in unscheduled_ids
            or str(task["task_id"]) not in scheduled_ids
        )
    ]


def render_empty_unresolved_list() -> None:
    st.markdown(
        """
        <div class="task-list-empty">
          <div class="task-list-empty-title">当前没有未安排任务</div>
          <div class="task-list-empty-copy">已排程任务会显示在上方当日任务里，完成按钮也在那里。</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def count_completed_tasks(tasks: List[Dict[str, Any]]) -> int:
    return sum(1 for task in tasks if task_status_value(task) == TaskStatus.DONE.value)


def count_tasks_by_status(tasks: List[Dict[str, Any]]) -> Dict[str, int]:
    counts = {status.value: 0 for status in TaskStatus}
    for task in tasks:
        counts[task_status_value(task)] += 1
    return counts


def render_unresolved_task_cards(tasks: List[Dict[str, Any]]) -> None:
    for task in tasks:
        render_unresolved_task_card(task)


def render_unresolved_task_card(task: Dict[str, Any]) -> None:
    card_key = f"unresolved_task_card_{dom_key(str(task['task_id']))}"
    inject_unresolved_card_style(card_key, task_status_value(task))
    with st.container(key=card_key):
        info_col, action_col = st.columns([5, 1])
        with info_col:
            st.markdown(unresolved_task_card_html(task), unsafe_allow_html=True)
        with action_col:
            if st.button(
                "自动加入",
                key=f"auto_join_{dom_key(str(task['task_id']))}",
                use_container_width=True,
                help="AI 在可行空档中选时段：遵守截止/不重叠/任务间距，不考虑专注与深度预算",
            ):
                request_force_join([str(task["task_id"])])
                st.rerun()
            if st.button("修改", key=f"edit_unresolved_{dom_key(str(task['task_id']))}", use_container_width=True):
                start_task_edit(str(task["task_id"]))
                st.rerun()


def inject_unresolved_card_style(card_key: str, status: str) -> None:
    border = "rgba(139, 92, 246, 0.54)" if status == TaskStatus.MISSED.value else "rgba(20, 184, 166, 0.34)"
    background = "rgba(139, 92, 246, 0.12)" if status == TaskStatus.MISSED.value else "rgba(255, 255, 255, 0.70)"
    st.markdown(
        f"""
        <style>
        .st-key-{card_key} {{
            background: {background};
            border-color: {border};
            backdrop-filter: blur(10px);
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_task_list_actions(
    tasks: List[Dict[str, Any]],
    status_counts: Dict[str, int],
) -> None:
    st.metric("未完成", count_unfinished_tasks(tasks))
    st.metric("已完成", status_counts[TaskStatus.DONE.value])
    st.metric("已超时", status_counts[TaskStatus.MISSED.value])

    if unresolved_count(tasks) > 0:
        if st.button(
            "全部自动加入日程",
            use_container_width=True,
            type="primary",
            help="将全部未排任务强制塞入现有日程空档",
        ):
            request_force_join([str(task["task_id"]) for task in unresolved_tasks(tasks)])
            st.rerun()

    delete_label = st.selectbox(
        "删除任务",
        options=[""] + [f"{task['title']} / {task['task_id']}" for task in tasks],
    )
    if st.button("删除选中任务", use_container_width=True, disabled=not delete_label):
        task_id = delete_label.split(" / ")[-1]
        remove_task(task_id)
        st.rerun()
    if st.button("清空任务列表", use_container_width=True):
        clear_tasks()
        st.rerun()


def unresolved_task_card_html(task: Dict[str, Any]) -> str:
    status = task_status_value(task)
    deadline = datetime.fromisoformat(str(task["deadline"]))
    return f"""
    <div class="unresolved-task-content">
      <div class="unresolved-task-head">
        <span>{html_escape(str(task["title"]))}</span>
        <strong>{status_label(status)}</strong>
      </div>
      <div class="unresolved-task-meta">
        <span>{html_escape(str(task.get("series_id") or "单独任务"))}</span>
        <span>{deadline_type_text(task)}</span>
        <span>{int(task["duration_min"])} 分钟</span>
        <span>DDL {deadline:%m-%d %H:%M}</span>
        <span>{environment_text(task.get("required_environment", ()))}</span>
      </div>
    </div>
    """


def update_task_statuses(done_by_id: Dict[str, bool]) -> bool:
    changed = False
    for task in st.session_state.pending_tasks:
        task_id = task["task_id"]
        if task_id not in done_by_id:
            continue
        current_status = task_status_value(task)
        next_status = resolve_next_status(current_status, done_by_id[task_id])
        if current_status == next_status:
            continue
        task["status"] = next_status
        record_operation(
            "task_status_changed",
            task_id=task_id,
            title=str(task.get("title", "")),
            detail=f"{current_status}->{next_status}",
        )
        changed = True
    return changed


def resolve_next_status(current_status: str, done_checked: bool) -> str:
    if done_checked and current_status != TaskStatus.DONE.value:
        return TaskStatus.DONE.value
    if not done_checked and current_status == TaskStatus.DONE.value:
        return TaskStatus.PENDING.value
    return current_status


def status_label(status: str) -> str:
    return STATUS_LABELS.get(status, status)


def unresolved_count(tasks: List[Dict[str, Any]]) -> int:
    return len(unresolved_tasks(tasks))


def count_unfinished_tasks(tasks: List[Dict[str, Any]]) -> int:
    finished_statuses = {TaskStatus.DONE.value, TaskStatus.CANCELLED.value}
    return sum(1 for task in tasks if task_status_value(task) not in finished_statuses)


def environment_text(environments: Any) -> str:
    if isinstance(environments, str):
        environments = [environments]
    labels = [ENVIRONMENT_LABELS.get(str(env), str(env)) for env in environments]
    return ", ".join(labels) or "-"


def html_escape(value: str) -> str:
    return html.escape(value)


def dom_key(value: str) -> str:
    return "".join(char if char.isalnum() else "_" for char in value)


def deadline_type_text(task: Dict[str, Any]) -> str:
    return "严格DDL" if str(task.get("deadline_type")) == "strict" else "期望DDL"
