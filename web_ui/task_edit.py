from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import streamlit as st

from models import DeadlineType, ScheduleBlock, ScheduleResult, TaskScore, TaskStatus, UserProfile
from web_ui.archive import record_operation, save_session_archive
from web_ui.constants import ENVIRONMENT_LABELS, ENVIRONMENT_OPTIONS
from web_ui.session_state import mark_schedule_dirty
from web_ui.task_data import task_status_value


def start_task_edit(task_id: str) -> None:
    st.session_state.edit_task_id = task_id


def render_task_edit_panel() -> None:
    task_id = st.session_state.get("edit_task_id")
    if not task_id:
        return

    task = raw_task_by_id(str(task_id))
    if task is None:
        st.session_state.edit_task_id = None
        return

    block = schedule_block_by_task_id(str(task_id))
    defaults = editor_defaults(task, block)

    _, center, _ = st.columns([0.35, 4.3, 0.35])
    with center:
        st.markdown('<div class="task-edit-shell">', unsafe_allow_html=True)
        st.subheader("修改任务")
        with st.form(f"task_edit_form_{task_id}", clear_on_submit=False, border=False):
            title = st.text_input("任务名称", value=str(task.get("title", "")))

            deadline_type = st.radio(
                "DDL 类型",
                options=[DeadlineType.STRICT.value, DeadlineType.FLEXIBLE.value],
                index=0 if str(task.get("deadline_type")) == DeadlineType.STRICT.value else 1,
                format_func=deadline_type_label,
                horizontal=True,
            )

            mode = st.radio(
                "任务类型",
                options=["单独任务", "系列任务"],
                index=1 if task.get("series_id") else 0,
                horizontal=True,
            )
            series_id = ""
            if mode == "系列任务":
                series_id = st.text_input("系列名称", value=str(task.get("series_id") or ""))

            time_cols = st.columns(3)
            start_date = time_cols[0].date_input("安排日期", value=defaults["start"].date())
            start_time = time_cols[1].time_input("开始时间", value=defaults["start"].time())
            duration_min = int(
                time_cols[2].number_input(
                    "任务用时（分钟）",
                    min_value=5,
                    max_value=24 * 60,
                    step=5,
                    value=int(task.get("duration_min", defaults["duration_min"])),
                )
            )

            start = datetime.combine(start_date, start_time).replace(second=0, microsecond=0)
            end = start + timedelta(minutes=duration_min)
            st.caption(f"手动安排时间段：{start:%Y-%m-%d %H:%M} - {end:%H:%M}")

            ddl_cols = st.columns(2)
            deadline_date = ddl_cols[0].date_input("DDL 日期", value=defaults["deadline"].date())
            deadline_time = ddl_cols[1].time_input("DDL 时间", value=defaults["deadline"].time())

            env_value = normalize_environment_selection(task.get("required_environment", ()))
            required_environment = st.multiselect(
                "任务环境",
                options=ENVIRONMENT_OPTIONS,
                default=env_value,
                format_func=lambda value: ENVIRONMENT_LABELS.get(value, value),
            )
            required_quietness = st.slider(
                "安静度需求",
                min_value=0.0,
                max_value=1.0,
                value=float(task.get("required_quietness", 0.0)),
                step=0.05,
            )

            action_cols = st.columns(2)
            with action_cols[0]:
                submitted = st.form_submit_button("保存修改", type="primary", use_container_width=True)
            with action_cols[1]:
                cancelled = st.form_submit_button("取消", use_container_width=True)

        st.markdown("</div>", unsafe_allow_html=True)

    if cancelled:
        st.session_state.edit_task_id = None
        st.rerun()
    if submitted:
        deadline = datetime.combine(deadline_date, deadline_time).replace(second=0, microsecond=0)
        validation_error = validate_editor_input(title, series_id, mode, start, deadline, duration_min)
        if validation_error:
            st.warning(validation_error)
            return
        save_task_edit(
            task_id=str(task_id),
            title=title.strip(),
            start=start,
            end=end,
            duration_min=duration_min,
            deadline=deadline,
            deadline_type=DeadlineType(deadline_type),
            series_id=series_id.strip() if mode == "系列任务" else None,
            required_environment=tuple(required_environment),
            required_quietness=required_quietness,
        )
        st.session_state.edit_task_id = None
        st.session_state.schedule_selected_day = start.date()
        st.rerun()


def raw_task_by_id(task_id: str) -> Optional[Dict[str, Any]]:
    return next(
        (task for task in st.session_state.pending_tasks if str(task.get("task_id")) == task_id),
        None,
    )


def schedule_block_by_task_id(task_id: str) -> Optional[ScheduleBlock]:
    result = st.session_state.get("last_result")
    if result is None:
        return None
    return next((block for block in result.blocks if block.task_id == task_id), None)


def editor_defaults(task: Dict[str, Any], block: Optional[ScheduleBlock]) -> Dict[str, Any]:
    start = block.start if block is not None else parse_optional_datetime(task.get("earliest_start"))
    if start is None:
        start = datetime.now().replace(second=0, microsecond=0)
    duration_min = int(task.get("duration_min", 30))
    deadline = parse_datetime(task.get("deadline")) or start + timedelta(hours=2)
    return {
        "start": start,
        "duration_min": duration_min,
        "deadline": deadline,
    }


def validate_editor_input(
    title: str,
    series_id: str,
    mode: str,
    start: datetime,
    deadline: datetime,
    duration_min: int,
) -> str:
    if not title.strip():
        return "任务名称不能为空。"
    if mode == "系列任务" and not series_id.strip():
        return "系列任务需要填写系列名称。"
    if duration_min < 5:
        return "任务用时至少 5 分钟。"
    if deadline <= start:
        return "DDL 需要晚于任务开始时间。"
    if start + timedelta(minutes=duration_min) > deadline:
        return "手动安排的结束时间不能晚于 DDL。"
    return ""


def save_task_edit(
    task_id: str,
    title: str,
    start: datetime,
    end: datetime,
    duration_min: int,
    deadline: datetime,
    deadline_type: DeadlineType,
    series_id: Optional[str],
    required_environment: tuple[str, ...],
    required_quietness: float,
) -> None:
    task = raw_task_by_id(task_id)
    if task is None:
        return

    previous_status = task_status_value(task)
    task.update(
        {
            "title": title,
            "duration_min": duration_min,
            "deadline": deadline.isoformat(),
            "earliest_start": start.isoformat(),
            "manual_start": start.isoformat(),
            "manual_end": end.isoformat(),
            "deadline_type": deadline_type.value,
            "series_id": series_id,
            "required_environment": required_environment,
            "required_quietness": required_quietness,
            "status": resolve_status_after_manual_schedule(previous_status),
            "deadline_overdue": False,
        }
    )

    record_operation(
        "task_manual_edited",
        task_id=task_id,
        title=title,
        detail=f"manual={start:%Y-%m-%d %H:%M}-{end:%H:%M}",
    )
    mark_schedule_dirty()


def resolve_status_after_manual_schedule(previous_status: str) -> str:
    if previous_status in {TaskStatus.DONE.value, TaskStatus.CANCELLED.value}:
        return previous_status
    return TaskStatus.PENDING.value


def upsert_manual_schedule_block(task_id: str, title: str, start: datetime, end: datetime) -> None:
    result = st.session_state.get("last_result")
    if result is None:
        result = ScheduleResult(blocks=[], unscheduled_task_ids=[], total_cost=0.0)

    existing = next((block for block in result.blocks if block.task_id == task_id), None)
    priority = existing.priority if existing else manual_priority(task_id)
    reason = f"手动安排：{start:%m-%d %H:%M} - {end:%H:%M}"
    next_block = ScheduleBlock(
        task_id=task_id,
        title=title,
        start=start,
        end=end,
        priority=priority,
        reason=reason,
    )
    next_blocks = [block for block in result.blocks if block.task_id != task_id]
    next_blocks.append(next_block)
    next_blocks.sort(key=lambda block: block.start)
    st.session_state.last_result = ScheduleResult(
        blocks=next_blocks,
        unscheduled_task_ids=[item for item in result.unscheduled_task_ids if item != task_id],
        total_cost=result.total_cost,
    )


def manual_priority(task_id: str) -> float:
    scores: Dict[str, TaskScore] | None = st.session_state.get("last_scores")
    profile: UserProfile | None = st.session_state.get("last_profile")
    if scores is None or profile is None or task_id not in scores:
        return 0.0
    return scores[task_id].priority(profile.weights)


def normalize_environment_selection(value: Any) -> list[str]:
    if isinstance(value, str):
        value = [value]
    return [str(item) for item in value if str(item) in ENVIRONMENT_OPTIONS]


def parse_datetime(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def parse_optional_datetime(value: Any) -> Optional[datetime]:
    return parse_datetime(value)


def deadline_type_label(value: str) -> str:
    if value == DeadlineType.STRICT.value:
        return "严格截止"
    return "期望截止"
