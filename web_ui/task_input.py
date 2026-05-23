from __future__ import annotations

import re
import uuid
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Optional

import streamlit as st

from agents import TaskParserAgent
from llm_client import DeepSeekLLMClient, LLMProviderError
from models import Task, TaskStatus, UserProfile, clamp01
from web_ui.constants import ENVIRONMENT_OPTIONS
from web_ui.profile import build_profile
from web_ui.session_state import mark_schedule_dirty
from web_ui.task_data import materialize_tasks


def render_task_form(profile_config: Dict[str, Any]) -> None:
    st.subheader("Task Input & Management")
    task_request = render_task_request_form()
    if task_request is None:
        return
    add_task_from_request(task_request, profile_config)


def render_task_request_form() -> Dict[str, Any] | None:
    with st.form("new_task_form", clear_on_submit=True):
        task_text = render_task_text_input()
        fixed_deadline = render_fixed_deadline_input()
        submitted = st.form_submit_button("让 AI 分析并添加任务", use_container_width=True)

    if not submitted:
        return None
    return {
        "task_text": task_text.strip(),
        "fixed_deadline": fixed_deadline,
    }


def render_task_text_input() -> str:
    return st.text_area(
        "告诉 AI 你要安排什么",
        placeholder=(
            "例如：我明天晚上前要提交数字电子技术实验报告，"
            "需要比较安静的环境，大概是深度工作，最好别安排得太碎。"
        ),
        height=132,
    )


def render_fixed_deadline_input() -> Optional[datetime]:
    has_fixed_deadline = st.checkbox("这个任务有固定 DDL")
    if not has_fixed_deadline:
        return None

    col_date, col_time = st.columns(2)
    fixed_date = col_date.date_input(
        "固定 DDL 日期",
        value=date.today() + timedelta(days=1),
    )
    fixed_time = col_time.time_input("固定 DDL 时间", value=time(18, 0))
    return datetime.combine(fixed_date, fixed_time)


def add_task_from_request(task_request: Dict[str, Any], profile_config: Dict[str, Any]) -> None:
    validation_error = validate_task_request(task_request, profile_config)
    if validation_error:
        st.warning(validation_error)
        return

    try:
        task_payload = create_task_payload(task_request, profile_config)
    except LLMProviderError as exc:
        st.error(f"AI 任务分析失败：{exc}")
        return
    except ValueError as exc:
        st.error(f"AI 解析结果不合法：{exc}")
        return
    except Exception as exc:  # pragma: no cover - UI safety net
        st.error(f"任务分析失败：{type(exc).__name__}: {exc}")
        return

    st.session_state.pending_tasks.append(task_payload)
    mark_schedule_dirty()
    show_task_added_message(task_payload)


def validate_task_request(task_request: Dict[str, Any], profile_config: Dict[str, Any]) -> str:
    if not task_request["task_text"]:
        return "请先告诉 AI 你要安排什么任务。"
    if not profile_config["api_key"]:
        return "请先在侧边栏输入 API Key，AI 才能分析任务。"
    fixed_deadline = task_request["fixed_deadline"]
    if fixed_deadline and fixed_deadline <= datetime.now():
        return "固定 DDL 需要晚于当前时间。"
    return ""


def create_task_payload(task_request: Dict[str, Any], profile_config: Dict[str, Any]) -> Dict[str, Any]:
    now = datetime.now().replace(second=0, microsecond=0)
    profile = build_profile(profile_config)
    existing_tasks = materialize_tasks(st.session_state.pending_tasks)
    parsed_task = parse_task_with_ai(
        task_text=task_request["task_text"],
        profile=profile,
        profile_config=profile_config,
        now=now,
        fixed_deadline=task_request["fixed_deadline"],
        existing_tasks=existing_tasks,
    )
    return build_task_payload_from_ai(
        parsed=parsed_task,
        source_text=task_request["task_text"],
        fixed_deadline=task_request["fixed_deadline"],
        now=now,
    )


def parse_task_with_ai(
    task_text: str,
    profile: UserProfile,
    profile_config: Dict[str, Any],
    now: datetime,
    fixed_deadline: Optional[datetime],
    existing_tasks: List[Task],
) -> Dict[str, Any]:
    parser = TaskParserAgent(llm_client=build_llm_client(profile_config))
    with st.spinner("AI 正在分析任务细节..."):
        return parser.parse_task(
            user_text=task_text,
            profile=profile,
            now=now,
            allowed_environment_options=ENVIRONMENT_OPTIONS,
            fixed_deadline=fixed_deadline,
            existing_tasks=existing_tasks,
        )


def build_llm_client(profile_config: Dict[str, Any]) -> DeepSeekLLMClient:
    return DeepSeekLLMClient(
        api_key=profile_config["api_key"],
        model=profile_config["model"],
        base_url=profile_config["base_url"],
    )


def build_task_payload_from_ai(
    parsed: Dict[str, Any],
    source_text: str,
    fixed_deadline: Optional[datetime],
    now: datetime,
) -> Dict[str, Any]:
    ensure_parsed_task_is_dict(parsed)
    deadline = resolve_deadline(parsed, fixed_deadline, now)
    earliest_start = resolve_earliest_start(parsed, now, deadline)
    return {
        "task_id": make_task_id(resolve_title(parsed, source_text)),
        "title": resolve_title(parsed, source_text),
        "description": resolve_description(parsed, source_text),
        "series_id": normalized_text(parsed.get("series_id")) or None,
        "duration_min": normalize_duration(parsed.get("duration_min")),
        "deadline": deadline.replace(second=0, microsecond=0).isoformat(),
        "earliest_start": earliest_start.replace(second=0, microsecond=0).isoformat(),
        "required_environment": tuple(normalize_environments(parsed.get("required_environment"))),
        "required_quietness": normalize_score(parsed.get("required_quietness"), default=0.45),
        "dependencies": normalize_dependencies(parsed.get("dependencies")),
        "status": TaskStatus.PENDING.value,
        "tags": tuple(normalize_tags(parsed.get("tags"))),
    }


def ensure_parsed_task_is_dict(parsed: Dict[str, Any]) -> None:
    if not isinstance(parsed, dict):
        raise ValueError("AI 必须返回 JSON object。")


def resolve_title(parsed: Dict[str, Any], source_text: str) -> str:
    return normalized_text(parsed.get("title")) or source_text[:28]


def resolve_description(parsed: Dict[str, Any], source_text: str) -> str:
    description = normalized_text(parsed.get("description")) or source_text
    assumptions = normalized_text(parsed.get("assumptions"))
    if assumptions:
        return f"{description}\n\nAI assumptions: {assumptions}"
    return description


def resolve_deadline(
    parsed: Dict[str, Any],
    fixed_deadline: Optional[datetime],
    now: datetime,
) -> datetime:
    deadline = fixed_deadline or parse_datetime_field(parsed.get("deadline"), "deadline")
    if deadline <= now:
        raise ValueError("AI 推断出的 DDL 已经过期，请在描述里补充更明确的时间。")
    return deadline


def resolve_earliest_start(parsed: Dict[str, Any], now: datetime, deadline: datetime) -> datetime:
    earliest_start = parse_optional_datetime_field(parsed.get("earliest_start"))
    if earliest_start is None or earliest_start < now or earliest_start >= deadline:
        return now
    return earliest_start


def normalize_dependencies(value: Any) -> tuple[str, ...]:
    valid_dependency_ids = {task["task_id"] for task in st.session_state.pending_tasks}
    return tuple(dep for dep in normalize_string_list(value) if dep in valid_dependency_ids)


def parse_datetime_field(value: Any, field_name: str) -> datetime:
    parsed = parse_optional_datetime_field(value)
    if parsed is None:
        raise ValueError(f"AI 缺少 {field_name}。")
    return parsed


def parse_optional_datetime_field(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw or raw.lower() == "null":
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"无法解析时间：{raw}") from exc
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone().replace(tzinfo=None)
    return parsed.replace(second=0, microsecond=0)


def normalize_duration(value: Any) -> int:
    try:
        duration = int(round(float(value) / 5) * 5)
    except (TypeError, ValueError):
        duration = 60
    return max(5, min(480, duration))


def normalize_score(value: Any, default: float) -> float:
    try:
        return clamp01(float(value))
    except (TypeError, ValueError):
        return clamp01(default)


def normalize_environments(value: Any) -> List[str]:
    allowed = set(ENVIRONMENT_OPTIONS)
    environments = [item for item in normalize_string_list(value) if item in allowed]
    return environments or ["desk"]


def normalize_tags(value: Any) -> List[str]:
    return [
        re.sub(r"\s+", "-", item.strip().lower())
        for item in normalize_string_list(value)
        if item.strip()
    ][:8]


def normalize_string_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw_items = value.split(",")
    elif isinstance(value, (list, tuple)):
        raw_items = value
    else:
        raw_items = [value]
    return [str(item).strip() for item in raw_items if str(item).strip()]


def normalized_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() == "null" else text


def make_task_id(title: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", title.strip().lower()).strip("-")
    if not slug:
        slug = "task"
    return f"{slug[:28]}-{uuid.uuid4().hex[:6]}"


def show_task_added_message(task_payload: Dict[str, Any]) -> None:
    deadline = datetime.fromisoformat(task_payload["deadline"])
    st.success(
        f"AI 已添加任务：{task_payload['title']} · "
        f"{task_payload['duration_min']} min · DDL {deadline:%m-%d %H:%M}"
    )

