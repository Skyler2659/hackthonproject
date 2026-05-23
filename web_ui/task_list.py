from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

import pandas as pd
import streamlit as st

from models import TaskStatus
from web_ui.archive import record_operation
from web_ui.constants import ENVIRONMENT_LABELS
from web_ui.session_state import mark_schedule_dirty
from web_ui.task_data import clear_tasks, remove_task, task_status_value


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
    tasks = st.session_state.pending_tasks
    st.markdown('<div class="task-list-shell">', unsafe_allow_html=True)
    st.subheader("任务列表")

    if not tasks:
        render_empty_task_list()
        st.markdown("</div>", unsafe_allow_html=True)
        return

    status_counts = count_tasks_by_status(tasks)
    col_left, col_right = st.columns([4, 1.2])
    with col_left:
        render_task_table(tasks)
    with col_right:
        render_task_list_actions(tasks, status_counts)
    st.markdown("</div>", unsafe_allow_html=True)


def render_empty_task_list() -> None:
    st.markdown(
        """
        <div class="task-list-empty">
          <div class="task-list-empty-title">当前还没有存档任务</div>
          <div class="task-list-empty-copy">任务列表会常驻在这里。你可以从页面底部的 AI 对话框添加新任务。</div>
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


def render_task_table(tasks: List[Dict[str, Any]]) -> None:
    edited_tasks = st.data_editor(
        tasks_to_dataframe(tasks),
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
        column_config={
            "完成": st.column_config.CheckboxColumn("完成"),
        },
        disabled=["任务 ID", "标题", "状态", "系列", "时长", "DDL", "安静度", "依赖", "环境"],
        key="task_status_editor",
    )
    if apply_status_edits(edited_tasks):
        st.rerun()


def render_task_list_actions(
    tasks: List[Dict[str, Any]],
    status_counts: Dict[str, int],
) -> None:
    st.metric("待排程", status_counts[TaskStatus.PENDING.value])
    st.metric("已完成", status_counts[TaskStatus.DONE.value])
    st.metric("已超时", status_counts[TaskStatus.MISSED.value])
    st.metric("历史操作", len(st.session_state.get("operation_history", [])))

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


def tasks_to_dataframe(tasks: List[Dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame([task_to_table_row(task) for task in tasks])


def task_to_table_row(task: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "完成": task_status_value(task) == TaskStatus.DONE.value,
        "任务 ID": task["task_id"],
        "标题": task["title"],
        "状态": status_label(task_status_value(task)),
        "系列": task.get("series_id") or "单独任务",
        "时长": f"{task['duration_min']} 分钟",
        "DDL": datetime.fromisoformat(task["deadline"]).strftime("%m-%d %H:%M"),
        "安静度": f"{float(task.get('required_quietness', 0.0)):.2f}",
        "依赖": ", ".join(task.get("dependencies", ())) or "-",
        "环境": environment_text(task.get("required_environment", ())),
    }


def apply_status_edits(edited_tasks: pd.DataFrame) -> bool:
    if "完成" not in edited_tasks or "任务 ID" not in edited_tasks:
        return False

    changed = update_task_statuses(read_done_values(edited_tasks))
    if changed:
        mark_schedule_dirty()
    return changed


def read_done_values(edited_tasks: pd.DataFrame) -> Dict[str, bool]:
    return {
        str(row["任务 ID"]): bool(row["完成"])
        for _, row in edited_tasks.iterrows()
    }


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


def environment_text(environments: Any) -> str:
    if isinstance(environments, str):
        environments = [environments]
    labels = [ENVIRONMENT_LABELS.get(str(env), str(env)) for env in environments]
    return ", ".join(labels) or "-"
