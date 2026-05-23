from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

import pandas as pd
import streamlit as st

from models import TaskStatus
from web_ui.session_state import mark_schedule_dirty
from web_ui.task_data import remove_task, task_status_value


def render_pending_tasks() -> None:
    tasks = st.session_state.pending_tasks
    if not tasks:
        st.info("当前待处理任务列表为空。先添加几个任务，再启动调度。")
        return

    completed_count = count_completed_tasks(tasks)
    pending_count = len(tasks) - completed_count
    col_left, col_right = st.columns([4, 1.2])
    with col_left:
        render_task_table(tasks)
    with col_right:
        render_task_list_actions(tasks, pending_count, completed_count)


def count_completed_tasks(tasks: List[Dict[str, Any]]) -> int:
    return sum(1 for task in tasks if task_status_value(task) == TaskStatus.DONE.value)


def render_task_table(tasks: List[Dict[str, Any]]) -> None:
    edited_tasks = st.data_editor(
        tasks_to_dataframe(tasks),
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
        column_config={
            "Done": st.column_config.CheckboxColumn("完成"),
        },
        disabled=["Task ID", "Title", "Series", "Duration", "DDL", "Quiet", "Deps", "Env"],
        key="task_status_editor",
    )
    if apply_status_edits(edited_tasks):
        st.rerun()


def render_task_list_actions(
    tasks: List[Dict[str, Any]],
    pending_count: int,
    completed_count: int,
) -> None:
    st.metric("待调度", pending_count)
    st.metric("已完成", completed_count)
    delete_label = st.selectbox(
        "删除任务",
        options=[""] + [f"{task['title']} / {task['task_id']}" for task in tasks],
    )
    if st.button("删除选中任务", use_container_width=True, disabled=not delete_label):
        task_id = delete_label.split(" / ")[-1]
        remove_task(task_id)
        st.rerun()
    if st.button("清空任务列表", use_container_width=True):
        st.session_state.pending_tasks = []
        mark_schedule_dirty()
        st.rerun()


def tasks_to_dataframe(tasks: List[Dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame([task_to_table_row(task) for task in tasks])


def task_to_table_row(task: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "Done": task_status_value(task) == TaskStatus.DONE.value,
        "Task ID": task["task_id"],
        "Title": task["title"],
        "Series": task.get("series_id") or "standalone",
        "Duration": f"{task['duration_min']} min",
        "DDL": datetime.fromisoformat(task["deadline"]).strftime("%m-%d %H:%M"),
        "Quiet": f"{float(task.get('required_quietness', 0.0)):.2f}",
        "Deps": ", ".join(task.get("dependencies", ())) or "-",
        "Env": ", ".join(task.get("required_environment", ())) or "-",
    }


def apply_status_edits(edited_tasks: pd.DataFrame) -> bool:
    if "Done" not in edited_tasks or "Task ID" not in edited_tasks:
        return False

    changed = update_task_statuses(read_done_values(edited_tasks))
    if changed:
        mark_schedule_dirty()
    return changed


def read_done_values(edited_tasks: pd.DataFrame) -> Dict[str, bool]:
    return {
        str(row["Task ID"]): bool(row["Done"])
        for _, row in edited_tasks.iterrows()
    }


def update_task_statuses(done_by_id: Dict[str, bool]) -> bool:
    changed = False
    for task in st.session_state.pending_tasks:
        task_id = task["task_id"]
        if task_id not in done_by_id:
            continue
        next_status = TaskStatus.DONE.value if done_by_id[task_id] else TaskStatus.PENDING.value
        if task_status_value(task) != next_status:
            task["status"] = next_status
            changed = True
    return changed

