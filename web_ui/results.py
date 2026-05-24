from __future__ import annotations

import hashlib
import html
import json
from dataclasses import replace
from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional

import streamlit as st
import streamlit.components.v1 as components

from models import DeadlineType, ScheduleResult, Task, TaskScore, TaskStatus, UserProfile, clamp01
from web_ui.archive import record_operation, save_session_archive
from web_ui.session_state import mark_schedule_dirty
from web_ui.task_data import materialize_tasks, task_status_value
from web_ui.task_edit import start_task_edit


DIMENSION_LABELS = {
    "cognitive_load": "认知负荷",
    "urgency": "紧急度",
    "confidence": "置信度",
}
CALENDAR_HOUR_HEIGHT = 46


def render_results() -> None:
    result = st.session_state.last_result
    scores = st.session_state.last_scores
    profile = st.session_state.last_profile
    if result is None or scores is None or profile is None:
        render_empty_results()
        return

    st.subheader("调度结果")
    refinement_summary = st.session_state.get("last_refinement_summary")
    if refinement_summary:
        st.info(f"AI 微调说明：{refinement_summary}")
    render_schedule_metrics(result)
    render_unscheduled_warning(result)
    tasks = task_lookup()
    day_tab, timeline_tab = st.tabs(["当日任务", "解释列表"])
    with day_tab:
        render_daily_task_list(result, tasks)
    with timeline_tab:
        render_schedule_timeline(result, scores, tasks, profile)


def render_empty_results() -> None:
    st.subheader("调度结果")
    day_tab, timeline_tab = st.tabs(["当日任务", "解释列表"])
    with day_tab:
        st.markdown(
            """
            <div class="day-list-empty">
              <div class="day-list-empty-title">当天任务会显示在这里</div>
              <div class="day-list-empty-copy">添加任务并完成一次调度后，任务会按日期分组排列。</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with timeline_tab:
        st.info("完成调度后，这里会展示每个任务块的安排原因。")


def render_schedule_metrics(result: ScheduleResult) -> None:
    metric_cols = st.columns(3)
    metric_cols[0].metric("已排程任务", scheduled_count(result))
    metric_cols[1].metric("未排入任务", unscheduled_count(result))
    metric_cols[2].metric("已完成任务", completed_count())


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
        score = scores.get(block.task_id)
        if score is None:
            continue
        render_schedule_block(index, block, score, tasks.get(block.task_id), profile)
    st.markdown("</div>", unsafe_allow_html=True)


def render_daily_task_list(result: ScheduleResult, tasks: Dict[str, Task]) -> None:
    init_day_state(result)
    render_day_nav(result)
    selected_day = selected_schedule_day(result)

    if not result.blocks:
        render_empty_day_frame(selected_day, has_schedule=False)
        return

    day_blocks = [
        block
        for block in sorted(result.blocks, key=lambda item: item.start)
        if block.start.date() == selected_day
    ]

    if not day_blocks:
        render_empty_day_frame(selected_day, has_schedule=True)
        return

    st.markdown(
        f'<div class="day-list-summary">{selected_day:%Y-%m-%d} · {len(day_blocks)} 个任务 · 按时间顺序排列</div>',
        unsafe_allow_html=True,
    )
    for block in day_blocks:
        render_day_task_card(block, tasks.get(block.task_id))


def render_empty_day_frame(selected_day: date, *, has_schedule: bool) -> None:
    if has_schedule:
        title = f"{selected_day:%Y-%m-%d} · {weekday_label(selected_day)}"
        copy = "这一天没有已排程任务，可用「上一天 / 下一天」查看其他日期。"
    else:
        title = f"{selected_day:%Y-%m-%d} · {weekday_label(selected_day)}"
        copy = "当前还没有成功排入日程的任务，添加任务并完成调度后会出现在对应日期。"
    st.markdown(
        f"""
        <div class="day-list-empty">
          <div class="day-list-empty-title">{html.escape(title)}</div>
          <div class="day-list-empty-copy">{html.escape(copy)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def init_day_state(result: ScheduleResult) -> None:
    dates = navigable_dates(result)
    if not dates:
        return
    selected_day = st.session_state.get("schedule_selected_day")
    if not isinstance(selected_day, date) or selected_day not in dates:
        st.session_state.schedule_selected_day = default_schedule_day(result, dates)


def render_day_nav(result: ScheduleResult) -> None:
    dates = navigable_dates(result)
    if not dates:
        return
    selected_day = selected_schedule_day(result)
    current_index = dates.index(selected_day)
    min_day, max_day = dates[0], dates[-1]

    left, center, right = st.columns([1, 3.2, 1])
    with left:
        if st.button(
            "上一天",
            use_container_width=True,
            disabled=selected_day <= min_day,
        ):
            st.session_state.schedule_selected_day = selected_day - timedelta(days=1)
            st.rerun()
    with center:
        selected = st.selectbox(
            "选择日期",
            options=dates,
            index=current_index,
            format_func=lambda value: date_option_label(value, result),
            label_visibility="collapsed",
        )
        st.session_state.schedule_selected_day = selected
    with right:
        if st.button(
            "下一天",
            use_container_width=True,
            disabled=selected_day >= max_day,
        ):
            st.session_state.schedule_selected_day = selected_day + timedelta(days=1)
            st.rerun()


def selected_schedule_day(result: ScheduleResult) -> date:
    selected_day = st.session_state.get("schedule_selected_day")
    dates = navigable_dates(result)
    if isinstance(selected_day, date) and selected_day in dates:
        return selected_day
    return default_schedule_day(result, dates)


def default_schedule_day(result: ScheduleResult, dates: list[date]) -> date:
    if not dates:
        return date.today()
    today = date.today()
    if today in dates:
        return today
    task_days = scheduled_dates(result)
    if task_days:
        return task_days[0]
    return dates[0]


def navigable_dates(result: ScheduleResult) -> list[date]:
    """Continuous calendar range from first to last scheduled block (includes empty days)."""
    if not result.blocks:
        return [date.today()]
    block_days = [block.start.date() for block in result.blocks]
    min_day = min(block_days)
    max_day = max(block_days)
    days: list[date] = []
    cursor = min_day
    while cursor <= max_day:
        days.append(cursor)
        cursor += timedelta(days=1)
    return days


def scheduled_dates(result: ScheduleResult) -> list[date]:
    return sorted({block.start.date() for block in result.blocks})


def weekday_label(value: date) -> str:
    day_names = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")
    return day_names[value.weekday()]


def date_option_label(value: date, result: ScheduleResult) -> str:
    count = sum(1 for block in result.blocks if block.start.date() == value)
    suffix = f"{count} 个任务" if count else "无任务"
    return f"{value:%Y-%m-%d} · {weekday_label(value)} · {suffix}"


def render_day_task_card(block: Any, task: Optional[Task]) -> None:
    container_key = f"day_task_card_{dom_key(block.task_id)}"
    palette = block_palette(block.task_id)
    inject_day_card_style(container_key, palette)

    with st.container(key=container_key):
        info_col, action_col = st.columns([5, 1])
        with info_col:
            st.markdown(day_task_card_content_html(block, task), unsafe_allow_html=True)
        with action_col:
            if task and task.status == TaskStatus.DONE:
                st.markdown('<div class="day-task-done-badge">已完成</div>', unsafe_allow_html=True)
            elif st.button("完成", key=f"complete_{dom_key(block.task_id)}", use_container_width=True):
                complete_scheduled_task(block.task_id)
                st.rerun()
            if st.button("修改", key=f"edit_{dom_key(block.task_id)}", use_container_width=True):
                start_task_edit(block.task_id)
                st.rerun()


def inject_day_card_style(container_key: str, palette: Dict[str, str]) -> None:
    st.markdown(
        f"""
        <style>
        .st-key-{container_key} {{
            background: {palette["bg"]};
            border-color: {palette["border"]};
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def day_task_card_content_html(block: Any, task: Optional[Task]) -> str:
    return f"""
    <div class="day-task-content" title="{safe(block.reason)}">
      <div class="day-task-time">
        <span>{block.start:%H:%M} - {block.end:%H:%M}</span>
        <strong>{duration_min(block)} 分钟</strong>
      </div>
      <div class="day-task-title">{safe(block.title)}</div>
      <div class="day-task-meta">
        <span>{safe(series_text(task))}</span>
        <span>{safe(deadline_type_text(task))}</span>
        <span>DDL {safe(deadline_text(task))}</span>
        <span>P {block.priority:.2f}</span>
      </div>
    </div>
    """


def complete_scheduled_task(task_id: str) -> None:
    changed = False
    title = ""
    for task in st.session_state.pending_tasks:
        if str(task.get("task_id")) != task_id:
            continue
        current_status = task_status_value(task)
        if current_status == TaskStatus.DONE.value:
            return
        task["status"] = TaskStatus.DONE.value
        title = str(task.get("title", ""))
        record_operation(
            "task_status_changed",
            task_id=task_id,
            title=title,
            detail=f"{current_status}->{TaskStatus.DONE.value}",
        )
        changed = True
        break

    if not changed:
        return

    mark_schedule_dirty()


def dom_key(value: str) -> str:
    return "".join(char if char.isalnum() else "_" for char in value)


def day_task_card_html(block: Any, task: Optional[Task]) -> str:
    palette = block_palette(block.task_id)
    return f"""
    <div class="day-task-card"
      title="{safe(block.reason)}"
      style="background:{palette['bg']}; border-color:{palette['border']};">
      <div class="day-task-time">
        <span>{block.start:%H:%M} - {block.end:%H:%M}</span>
        <strong>{duration_min(block)} 分钟</strong>
      </div>
      <div class="day-task-title">{safe(block.title)}</div>
      <div class="day-task-meta">
        <span>{safe(series_text(task))}</span>
        <span>DDL {safe(deadline_text(task))}</span>
        <span>P {block.priority:.2f}</span>
      </div>
    </div>
    """


def init_week_state(result: ScheduleResult) -> None:
    if "calendar_week_start" not in st.session_state:
        st.session_state.calendar_week_start = monday_of(first_block_date(result))


def render_calendar_edit_toggle() -> None:
    label = "退出修改模式" if st.session_state.get("calendar_edit_mode", False) else "修改日程"
    help_text = "进入后拖动单个日程到新的日期和时间，再点击确认修改完成。"
    if st.button(label, help=help_text):
        st.session_state.calendar_edit_mode = not st.session_state.get("calendar_edit_mode", False)
        st.rerun()


def apply_calendar_patch_from_query() -> None:
    payload = read_query_param("schedule_patch")
    if not payload:
        return
    clear_query_param("schedule_patch")
    try:
        patches = json.loads(payload)
    except json.JSONDecodeError:
        st.warning("没有读懂这次拖拽修改，请再试一次。")
        return
    if apply_schedule_patches(patches):
        st.session_state.calendar_edit_mode = False
        st.success("日程时间已更新，列表和解释视图也同步好了。")
        st.rerun()


def read_query_param(key: str) -> str:
    if hasattr(st, "query_params"):
        value = st.query_params.get(key, "")
    else:
        value = st.experimental_get_query_params().get(key, [""])[0]
    if isinstance(value, list):
        return str(value[0]) if value else ""
    return str(value)


def clear_query_param(key: str) -> None:
    if hasattr(st, "query_params"):
        if key in st.query_params:
            del st.query_params[key]
    else:
        params = st.experimental_get_query_params()
        params.pop(key, None)
        st.experimental_set_query_params(**params)


def apply_schedule_patches(patches: list[Dict[str, Any]]) -> bool:
    result = st.session_state.last_result
    if result is None:
        return False
    patch_by_task = {str(item.get("task_id")): item for item in patches if item.get("task_id")}
    changed = False
    next_blocks = []
    for block in result.blocks:
        patch = patch_by_task.get(block.task_id)
        if not patch:
            next_blocks.append(block)
            continue
        try:
            start = datetime.fromisoformat(str(patch["start"]))
            end = datetime.fromisoformat(str(patch["end"]))
        except (KeyError, ValueError):
            next_blocks.append(block)
            continue
        if start >= end:
            next_blocks.append(block)
            continue
        changed |= start != block.start or end != block.end
        next_blocks.append(replace(block, start=start, end=end))
        sync_task_manual_time(block.task_id, start)
    if not changed:
        return False
    next_blocks.sort(key=lambda item: item.start)
    st.session_state.last_result = ScheduleResult(
        blocks=next_blocks,
        unscheduled_task_ids=result.unscheduled_task_ids,
        total_cost=result.total_cost,
    )
    save_session_archive()
    record_operation("schedule_manually_moved", detail=f"moved={len(patch_by_task)}")
    return True


def sync_task_manual_time(task_id: str, start: datetime) -> None:
    for task in st.session_state.pending_tasks:
        if str(task.get("task_id")) == task_id:
            task["earliest_start"] = start.replace(second=0, microsecond=0).isoformat()
            break


def render_week_nav() -> None:
    left, center, right = st.columns([1, 3.2, 1])
    with left:
        if st.button("上一周", use_container_width=True):
            st.session_state.calendar_week_start -= timedelta(days=7)
            st.rerun()
    with center:
        week_start = st.session_state.calendar_week_start
        st.markdown(
            f'<div class="calendar-week-title">{week_start:%Y-%m-%d} - {(week_start + timedelta(days=6)):%m-%d}</div>',
            unsafe_allow_html=True,
        )
    with right:
        if st.button("下一周", use_container_width=True):
            st.session_state.calendar_week_start += timedelta(days=7)
            st.rerun()


def selected_week_start(result: ScheduleResult) -> date:
    week_start = st.session_state.get("calendar_week_start")
    if isinstance(week_start, date):
        return week_start
    return monday_of(first_block_date(result))


def first_block_date(result: ScheduleResult) -> date:
    return min(block.start.date() for block in result.blocks)


def monday_of(value: date) -> date:
    return value - timedelta(days=value.weekday())


def calendar_hour_bounds(week_blocks: list[Any], result: ScheduleResult) -> tuple[int, int]:
    source_blocks = week_blocks or result.blocks
    first_hour = min(block.start.hour for block in source_blocks)
    last_hour = max(ceil_hour(block.end) for block in source_blocks)
    return max(0, min(8, first_hour)), min(24, max(22, last_hour))


def ceil_hour(value: datetime) -> int:
    return value.hour + (1 if value.minute or value.second or value.microsecond else 0)


def calendar_html(
    week_start: date,
    blocks: list[Any],
    tasks: Dict[str, Task],
    day_start_hour: int,
    day_end_hour: int,
) -> str:
    hours = list(range(day_start_hour, day_end_hour + 1))
    body_height = max(1, day_end_hour - day_start_hour) * CALENDAR_HOUR_HEIGHT
    days = [week_start + timedelta(days=offset) for offset in range(7)]
    blocks_by_day = group_blocks_by_day(blocks)
    return f"""
    <div class="calendar-shell">
      <div class="calendar-grid">
        <div class="calendar-time-column">
          <div class="calendar-corner">时间</div>
          <div class="calendar-time-body" style="height:{body_height}px;">
            {''.join(time_label_html(hour, day_start_hour) for hour in hours)}
          </div>
        </div>
        {''.join(day_column_html(day, blocks_by_day.get(day, []), tasks, day_start_hour, body_height) for day in days)}
      </div>
    </div>
    """


def calendar_editor_html(
    week_start: date,
    blocks: list[Any],
    tasks: Dict[str, Task],
    day_start_hour: int,
    day_end_hour: int,
) -> str:
    hours = list(range(day_start_hour, day_end_hour + 1))
    body_height = max(1, day_end_hour - day_start_hour) * CALENDAR_HOUR_HEIGHT
    days = [week_start + timedelta(days=offset) for offset in range(7)]
    blocks_by_day = group_blocks_by_day(blocks)
    payload = json.dumps(
        [
            {
                "task_id": block.task_id,
                "duration_min": duration_min(block),
                "start": block.start.isoformat(),
                "end": block.end.isoformat(),
            }
            for block in blocks
        ],
        ensure_ascii=False,
    )
    return f"""
    <html>
    <head>
      <style>
        body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #0f172a; }}
        .edit-note {{ margin: 0 0 10px 0; padding: 10px 12px; border: 1px solid rgba(14,165,233,.26); border-radius: 8px; background: rgba(240,249,255,.9); font-size: 14px; }}
        .edit-actions {{ display:flex; gap: 8px; margin: 0 0 10px 0; align-items: center; }}
        .edit-actions button {{ border: 0; border-radius: 999px; padding: 8px 14px; font-weight: 750; cursor: pointer; }}
        #confirm {{ background: #0ea5e9; color: white; }}
        #reset {{ background: rgba(148,163,184,.18); color: #334155; }}
        .calendar-grid {{ min-width: 920px; display: grid; grid-template-columns: 82px repeat(7, minmax(112px, 1fr)); border: 1px solid rgba(148, 163, 184, 0.34); border-radius: 8px; overflow: hidden; background: rgba(255,255,255,.64); }}
        .calendar-time-column, .calendar-day-column {{ border-right: 1px solid rgba(148,163,184,.22); background: rgba(248,250,252,.62); }}
        .calendar-day-column:last-child {{ border-right: 0; }}
        .calendar-corner, .calendar-day-head {{ height: 48px; display:flex; align-items:center; justify-content:center; border-bottom:1px solid rgba(148,163,184,.26); background:rgba(241,245,249,.72); color:#334155; font-size:13px; font-weight:750; box-sizing:border-box; }}
        .calendar-day-head {{ flex-direction: column; gap: 1px; }}
        .calendar-day-head span {{ color: #0f172a; }}
        .calendar-day-head strong {{ color:#64748b; font-size: 11px; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }}
        .calendar-time-body, .calendar-day-body {{ position: relative; }}
        .calendar-day-body {{ background: repeating-linear-gradient(to bottom, rgba(148,163,184,.18) 0, rgba(148,163,184,.18) 1px, transparent 1px, transparent {CALENDAR_HOUR_HEIGHT}px), rgba(255,255,255,.54); }}
        .calendar-time-label {{ position:absolute; right:11px; color:#475569; font-size:12px; font-weight:650; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; white-space:nowrap; }}
        .calendar-task-block {{ position:absolute; left:8px; right:8px; border:2px solid rgba(14,165,233,.72); border-radius:16px; padding:5px 7px; box-shadow:0 10px 24px rgba(15,23,42,.12); overflow:hidden; color:#0f172a; cursor:grab; user-select:none; box-sizing:border-box; touch-action:none; }}
        .calendar-task-block.dragging {{ cursor:grabbing; opacity:.88; transform:scale(.99); z-index: 20; }}
        .calendar-task-time {{ font-size:10px; color:#475569; font-family:ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; white-space:nowrap; }}
        .calendar-task-title {{ margin-top:2px; font-size:12px; font-weight:750; line-height:1.22; overflow-wrap:anywhere; }}
        .calendar-task-meta {{ margin-top:2px; font-size:10px; color:#64748b; line-height:1.2; overflow-wrap:anywhere; }}
      </style>
    </head>
    <body>
      <div class="edit-note"><b>拖动日程块</b>到新的日期和时间。系统会按 15 分钟自动吸附，并保持原来的任务时长。</div>
      <div class="edit-actions">
        <button id="confirm">确认修改完成</button>
        <button id="reset">撤销本轮拖动</button>
      </div>
      <div class="calendar-grid" id="calendar-grid" data-day-start="{day_start_hour}" data-hour-height="{CALENDAR_HOUR_HEIGHT}">
        <div class="calendar-time-column">
          <div class="calendar-corner">时间</div>
          <div class="calendar-time-body" style="height:{body_height}px;">
            {''.join(time_label_html(hour, day_start_hour) for hour in hours)}
          </div>
        </div>
        {''.join(day_column_html(day, blocks_by_day.get(day, []), tasks, day_start_hour, body_height) for day in days)}
      </div>
      <script>
        const original = {payload};
        const dayDates = {json.dumps([day.isoformat() for day in days])};
        const grid = document.getElementById('calendar-grid');
        const dayStart = Number(grid.dataset.dayStart);
        const hourHeight = Number(grid.dataset.hourHeight);
        const columnBodies = Array.from(document.querySelectorAll('.calendar-day-body'));
        let active = null;
        let offsetY = 0;

        function pad(value) {{ return String(value).padStart(2, '0'); }}
        function minutesToTime(total) {{
          const hour = Math.floor(total / 60);
          const minute = total % 60;
          return `${{pad(hour)}}:${{pad(minute)}}`;
        }}
        function isoAt(dayIndex, minutes) {{
          const date = new Date(`${{dayDates[dayIndex]}}T00:00:00`);
          date.setMinutes(minutes);
          return `${{date.getFullYear()}}-${{pad(date.getMonth() + 1)}}-${{pad(date.getDate())}}T${{pad(date.getHours())}}:${{pad(date.getMinutes())}}:00`;
        }}
        function paintTime(block, startMinutes) {{
          const duration = Number(block.dataset.duration);
          block.dataset.startMinutes = String(startMinutes);
          block.querySelector('.calendar-task-time').textContent = `${{minutesToTime(startMinutes)}} - ${{minutesToTime(startMinutes + duration)}}`;
        }}
        function moveBlock(block, body, y) {{
          const maxTop = Math.max(0, body.clientHeight - block.offsetHeight);
          const snappedTop = Math.max(0, Math.min(maxTop, Math.round(y / (hourHeight / 4)) * (hourHeight / 4)));
          body.appendChild(block);
          block.style.top = `${{snappedTop}}px`;
          const startMinutes = dayStart * 60 + Math.round(snappedTop / hourHeight * 60 / 15) * 15;
          block.dataset.dayIndex = String(columnBodies.indexOf(body));
          paintTime(block, startMinutes);
        }}
        document.querySelectorAll('.calendar-task-block').forEach((block) => {{
          block.addEventListener('pointerdown', (event) => {{
            active = block;
            block.classList.add('dragging');
            block.setPointerCapture(event.pointerId);
            offsetY = event.clientY - block.getBoundingClientRect().top;
          }});
          block.addEventListener('pointermove', (event) => {{
            if (active !== block) return;
            const target = columnBodies.find((body) => {{
              const rect = body.getBoundingClientRect();
              return event.clientX >= rect.left && event.clientX <= rect.right;
            }}) || block.parentElement;
            const rect = target.getBoundingClientRect();
            moveBlock(block, target, event.clientY - rect.top - offsetY);
          }});
          block.addEventListener('pointerup', () => {{
            if (active !== block) return;
            block.classList.remove('dragging');
            active = null;
          }});
        }});
        document.getElementById('reset').addEventListener('click', () => window.location.reload());
        document.getElementById('confirm').addEventListener('click', () => {{
          const patches = Array.from(document.querySelectorAll('.calendar-task-block')).map((block) => {{
            const dayIndex = Number(block.dataset.dayIndex);
            const startMinutes = Number(block.dataset.startMinutes);
            const duration = Number(block.dataset.duration);
            const start = isoAt(dayIndex, startMinutes);
            const end = isoAt(dayIndex, startMinutes + duration);
            return {{ task_id: block.dataset.taskId, start, end }};
          }});
          const params = new URLSearchParams(window.parent.location.search);
          params.set('schedule_patch', JSON.stringify(patches));
          window.parent.location.href = `${{window.parent.location.pathname}}?${{params.toString()}}`;
        }});
      </script>
    </body>
    </html>
    """


def group_blocks_by_day(blocks: list[Any]) -> Dict[date, list[Any]]:
    grouped: Dict[date, list[Any]] = {}
    for block in blocks:
        grouped.setdefault(block.start.date(), []).append(block)
    return grouped


def time_label_html(hour: int, day_start_hour: int) -> str:
    top = (hour - day_start_hour) * CALENDAR_HOUR_HEIGHT + 6
    return f'<div class="calendar-time-label" style="top:{top}px;">{hour:02d}:00</div>'


def day_column_html(
    day: date,
    blocks: list[Any],
    tasks: Dict[str, Task],
    day_start_hour: int,
    body_height: int,
) -> str:
    day_names = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")
    return f"""
    <div class="calendar-day-column">
      <div class="calendar-day-head">
        <span>{day_names[day.weekday()]}</span>
        <strong>{day:%m-%d}</strong>
      </div>
      <div class="calendar-day-body" style="height:{body_height}px;">
        {''.join(calendar_block_html(block, tasks.get(block.task_id), day_start_hour) for block in blocks)}
      </div>
    </div>
    """


def calendar_block_html(block: Any, task: Optional[Task], day_start_hour: int) -> str:
    palette = block_palette(block.task_id)
    start_minutes = minutes_since_day_start(block.start, day_start_hour)
    duration = max(15, duration_min(block))
    top = start_minutes / 60 * CALENDAR_HOUR_HEIGHT
    height = max(30, duration / 60 * CALENDAR_HOUR_HEIGHT)
    return f"""
    <div class="calendar-task-block"
      data-task-id="{safe(block.task_id)}"
      data-duration="{duration}"
      data-start-minutes="{block.start.hour * 60 + block.start.minute}"
      data-day-index="{block.start.weekday()}"
      title="{safe(block.reason)}"
      style="top:{top:.1f}px; height:{height:.1f}px; background:{palette['bg']}; border-color:{palette['border']};">
      <div class="calendar-task-time">{block.start:%H:%M} - {block.end:%H:%M}</div>
      <div class="calendar-task-title">{safe(block.title)}</div>
      <div class="calendar-task-meta">{safe(series_text(task))} · P {block.priority:.2f}</div>
    </div>
    """


def minutes_since_day_start(moment: datetime, day_start_hour: int) -> int:
    return max(0, moment.hour * 60 + moment.minute - day_start_hour * 60)


def block_palette(task_id: str) -> Dict[str, str]:
    palettes = [
        {"bg": "rgba(14, 165, 233, 0.20)", "border": "rgba(14, 165, 233, 0.68)"},
        {"bg": "rgba(16, 185, 129, 0.20)", "border": "rgba(16, 185, 129, 0.68)"},
        {"bg": "rgba(245, 158, 11, 0.20)", "border": "rgba(245, 158, 11, 0.68)"},
        {"bg": "rgba(99, 102, 241, 0.18)", "border": "rgba(99, 102, 241, 0.62)"},
        {"bg": "rgba(236, 72, 153, 0.16)", "border": "rgba(236, 72, 153, 0.56)"},
        {"bg": "rgba(20, 184, 166, 0.20)", "border": "rgba(20, 184, 166, 0.66)"},
        {"bg": "rgba(132, 204, 22, 0.20)", "border": "rgba(101, 163, 13, 0.62)"},
    ]
    digest = hashlib.sha1(task_id.encode("utf-8")).hexdigest()
    return palettes[int(digest[:2], 16) % len(palettes)]


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


def deadline_type_text(task: Optional[Task]) -> str:
    if task and task.deadline_type == DeadlineType.STRICT:
        return "严格DDL"
    return "期望DDL"


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
