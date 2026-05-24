from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import streamlit as st

from agents import TaskParserAgent
from llm_client import DeepSeekLLMClient, LLMProviderError
from models import DeadlineType, Task, TaskStatus, UserProfile, clamp01
from web_ui.archive import record_operation
from web_ui.constants import ENVIRONMENT_OPTIONS
from web_ui.profile import build_profile
from web_ui.session_state import mark_schedule_dirty
from web_ui.task_data import materialize_tasks


def render_task_form(profile_config: Dict[str, Any]) -> None:
    from web_ui.task_clarification import render_task_clarification_dialog

    render_task_clarification_dialog(profile_config)
    render_task_added_notice()
    task_request = render_task_request_form()
    if task_request is None:
        return
    add_task_from_request(task_request, profile_config)


def render_task_added_notice() -> None:
    notice = st.session_state.get("task_added_notice", "")
    if not notice:
        return
    st.success(notice)
    st.session_state.task_added_notice = ""


def render_task_request_form() -> Dict[str, Any] | None:
    _, center, _ = st.columns([0.35, 4.3, 0.35])
    with center:
        with st.container(key="task_composer"):
            with st.form("new_task_form", clear_on_submit=True, border=False):
                st.markdown(
                    '<div class="composer-greeting">今天有什么要忙的吗？</div>',
                    unsafe_allow_html=True,
                )
                task_text = st.text_area(
                    "任务描述",
                    placeholder=(
                        "例如：我明天晚上前要提交数字电子技术实验报告，"
                        "需要比较安静的环境，大概是深度工作，最好别安排得太碎。"
                    ),
                    height=104,
                    label_visibility="collapsed",
                )
                submitted = st.form_submit_button("让 AI 分析并添加任务", use_container_width=True)

    if not submitted:
        return None
    return {
        "task_text": task_text.strip(),
        "fixed_deadline": None,
    }


def add_task_from_request(task_request: Dict[str, Any], profile_config: Dict[str, Any]) -> None:
    validation_error = validate_task_request(task_request, profile_config)
    if validation_error:
        st.warning(validation_error)
        return

    if not task_request.get("_skip_clarification"):
        from web_ui.task_clarification import assess_task_clarification, start_clarification_pending

        fixed_window = infer_fixed_time_window(
            task_request["task_text"],
            datetime.now().replace(second=0, microsecond=0),
        )
        deadline_type = infer_deadline_type(task_request["task_text"])
        if deadline_type is None and fixed_window is not None:
            deadline_type = DeadlineType.STRICT
        pending = None if fixed_window is not None else assess_task_clarification(task_request, profile_config)
        if deadline_type is None:
            pending = with_deadline_type_question(task_request, pending)
        else:
            task_request["_deadline_type"] = deadline_type.value
        if pending is not None:
            start_clarification_pending(pending)
            st.rerun()
            return

    try:
        task_payloads = create_task_payloads(task_request, profile_config)
    except LLMProviderError as exc:
        fallback_payload = build_fixed_window_fallback_payload(task_request["task_text"])
        if fallback_payload is not None:
            st.info("AI 请求没有成功，但这条固定时间段任务已经能本地识别，已按固定时间段加入。")
            finalize_added_tasks([fallback_payload])
            return
        st.error(f"AI 任务分析失败：{exc}")
        return
    except ValueError as exc:
        st.error(f"AI 解析结果不合法：{exc}")
        return
    except Exception as exc:  # pragma: no cover - UI safety net
        st.error(f"任务分析失败：{type(exc).__name__}: {exc}")
        return

    finalize_added_tasks(task_payloads)


def finalize_added_tasks(task_payloads: List[Dict[str, Any]]) -> None:
    st.session_state.pending_tasks.extend(task_payloads)
    record_added_tasks(task_payloads)
    mark_schedule_dirty()
    show_task_added_message(task_payloads)
    st.rerun()


def build_fixed_window_fallback_payload(source_text: str) -> Dict[str, Any] | None:
    now = datetime.now().replace(second=0, microsecond=0)
    fixed_window = infer_fixed_time_window(source_text, now)
    if fixed_window is None:
        return None
    start, end = fixed_window
    title = fixed_window_title(source_text)
    return {
        "task_id": unique_task_id(title, existing_task_ids()),
        "title": title,
        "description": source_text,
        "series_id": None,
        "duration_min": int((end - start).total_seconds() // 60),
        "deadline": end.isoformat(),
        "deadline_type": DeadlineType.STRICT.value,
        "earliest_start": start.isoformat(),
        "manual_start": start.isoformat(),
        "manual_end": end.isoformat(),
        "required_environment": ("desk",),
        "required_quietness": 0.35,
        "dependencies": (),
        "must_be_contiguous": False,
        "status": TaskStatus.PENDING.value,
        "tags": ("固定时间段",),
    }


def fixed_window_title(source_text: str) -> str:
    title = re.sub(
        r"(今天|今晚|明天|明早|明晚|明日|后天|大后天|上午|下午|晚上|早上|中午)",
        "",
        source_text,
    )
    title = re.sub(
        r"\d{1,2}(?:\s*[:：点]\s*\d{1,2})?\s*(?:-|~|～|到|至|—|－)\s*"
        r"\d{1,2}(?:\s*[:：点]\s*\d{1,2})?\s*(?:点|分)?",
        "",
        title,
    )
    title = re.sub(
        r"[零〇一二两三四五六七八九十]{1,4}(?:\s*点\s*半?)?\s*(?:-|~|～|到|至|—|－)\s*"
        r"[零〇一二两三四五六七八九十]{1,4}(?:\s*点\s*半?)?",
        "",
        title,
    )
    title = re.sub(r"^(有|要|需要|参加|去)\s*", "", title.strip())
    return title[:28] or "固定时间段任务"


def validate_task_request(task_request: Dict[str, Any], profile_config: Dict[str, Any]) -> str:
    if not task_request["task_text"]:
        return "请先告诉 AI 你要安排什么任务。"
    if not profile_config["api_key"]:
        return "请先在侧边栏输入 API Key，AI 才能分析任务。"
    return ""


def create_task_payloads(task_request: Dict[str, Any], profile_config: Dict[str, Any]) -> List[Dict[str, Any]]:
    now = datetime.now().replace(second=0, microsecond=0)
    profile = build_profile(profile_config)
    existing_tasks = materialize_tasks(st.session_state.pending_tasks)
    parsed_response = parse_task_with_ai(
        task_text=task_request["task_text"],
        profile=profile,
        profile_config=profile_config,
        now=now,
        fixed_deadline=task_request["fixed_deadline"],
        existing_tasks=existing_tasks,
    )
    parsed_tasks = extract_tasks_from_response(parsed_response)
    return build_task_payloads_from_ai(
        parsed_tasks=parsed_tasks,
        source_text=task_request["task_text"],
        fixed_deadline=task_request["fixed_deadline"],
        now=now,
        explicit_deadline_type=task_request.get("_deadline_type"),
    )


def extract_tasks_from_response(parsed_response: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not isinstance(parsed_response, dict):
        raise ValueError("AI 必须返回 JSON 对象。")
    tasks = parsed_response.get("tasks")
    if not isinstance(tasks, list) or len(tasks) == 0:
        if parsed_response.get("title"):
            return [parsed_response]
        raise ValueError("AI 返回的任务列表为空。")
    if not all(isinstance(task, dict) for task in tasks):
        raise ValueError("AI 返回的任务格式不正确。")
    return tasks


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


def build_task_payloads_from_ai(
    parsed_tasks: List[Dict[str, Any]],
    source_text: str,
    fixed_deadline: Optional[datetime],
    now: datetime,
    explicit_deadline_type: Any = None,
) -> List[Dict[str, Any]]:
    task_id_map = build_task_id_map(parsed_tasks, source_text)
    return [
        build_task_payload_from_ai(parsed, source_text, fixed_deadline, now, task_id_map, explicit_deadline_type)
        for parsed in parsed_tasks
    ]


def build_task_id_map(parsed_tasks: List[Dict[str, Any]], source_text: str) -> Dict[str, str]:
    task_id_map: Dict[str, str] = {}
    used_ids = existing_task_ids()
    for parsed in parsed_tasks:
        ai_task_id = normalized_text(parsed.get("task_id"))
        generated_id = unique_task_id(resolve_title(parsed, source_text), used_ids)
        if ai_task_id:
            task_id_map[ai_task_id] = generated_id
        used_ids.add(generated_id)
    return task_id_map


def existing_task_ids() -> set[str]:
    return {str(task["task_id"]) for task in st.session_state.pending_tasks}


def unique_task_id(title: str, used_ids: set[str]) -> str:
    while True:
        task_id = make_task_id(title)
        if task_id not in used_ids:
            return task_id


def build_task_payload_from_ai(
    parsed: Dict[str, Any],
    source_text: str,
    fixed_deadline: Optional[datetime],
    now: datetime,
    task_id_map: Dict[str, str],
    explicit_deadline_type: Any = None,
) -> Dict[str, Any]:
    ensure_parsed_task_is_dict(parsed)
    fixed_window = resolve_fixed_time_window(parsed, source_text, now)
    if fixed_window is not None:
        manual_start, manual_end = fixed_window
        duration_min = int((manual_end - manual_start).total_seconds() // 60)
        deadline = manual_end
        earliest_start = manual_start
        resolved_deadline_type = DeadlineType.STRICT
    else:
        manual_start = None
        manual_end = None
        duration_min = normalize_duration(parsed.get("duration_min"))
        deadline = resolve_deadline(parsed, fixed_deadline, now, source_text)
        earliest_start = resolve_earliest_start(parsed, now, deadline)
        resolved_deadline_type = normalize_deadline_type(
            explicit_deadline_type
            or parsed.get("deadline_type")
            or infer_deadline_type(source_text)
            or DeadlineType.FLEXIBLE
        )
    source_task_id = normalized_text(parsed.get("task_id"))
    return {
        "task_id": task_id_map.get(source_task_id) or unique_task_id(resolve_title(parsed, source_text), existing_task_ids()),
        "title": resolve_title(parsed, source_text),
        "description": resolve_description(parsed, source_text),
        "series_id": normalized_text(parsed.get("series_id")) or None,
        "duration_min": duration_min,
        "deadline": deadline.replace(second=0, microsecond=0).isoformat(),
        "deadline_type": resolved_deadline_type.value,
        "earliest_start": earliest_start.replace(second=0, microsecond=0).isoformat(),
        "manual_start": manual_start.replace(second=0, microsecond=0).isoformat() if manual_start else None,
        "manual_end": manual_end.replace(second=0, microsecond=0).isoformat() if manual_end else None,
        "required_environment": tuple(normalize_environments(parsed.get("required_environment"))),
        "required_quietness": normalize_score(parsed.get("required_quietness"), default=0.45),
        "dependencies": normalize_dependencies(parsed.get("dependencies"), task_id_map),
        "must_be_contiguous": normalize_bool(parsed.get("must_be_contiguous"), default=True),
        "deep_work_min": normalize_deep_work_min(parsed, duration_min),
        "status": TaskStatus.PENDING.value,
        "tags": tuple(normalize_tags(parsed.get("tags"))),
    }


def normalize_deep_work_min(parsed: Dict[str, Any], duration_min: int) -> int | None:
    if "deep_work_min" not in parsed:
        return None
    value = parsed.get("deep_work_min")
    if value is None:
        return None
    return max(0, min(int(value), duration_min))


def ensure_parsed_task_is_dict(parsed: Dict[str, Any]) -> None:
    if not isinstance(parsed, dict):
        raise ValueError("AI 必须返回 JSON 对象。")


def resolve_fixed_time_window(
    parsed: Dict[str, Any],
    source_text: str,
    now: datetime,
) -> Optional[tuple[datetime, datetime]]:
    explicit_start = parse_optional_datetime_like(
        parsed.get("fixed_start") or parsed.get("manual_start") or parsed.get("start")
    )
    explicit_end = parse_optional_datetime_like(
        parsed.get("fixed_end") or parsed.get("manual_end") or parsed.get("end")
    )
    if explicit_start is not None and explicit_end is not None and explicit_start < explicit_end:
        if explicit_end <= now:
            raise ValueError("固定时间段已经过去，请重新给出未来时间。")
        return explicit_start.replace(second=0, microsecond=0), explicit_end.replace(second=0, microsecond=0)

    return infer_fixed_time_window(source_text, now)


def parse_optional_datetime_like(value: Any) -> Optional[datetime]:
    try:
        return parse_optional_datetime_field(value)
    except ValueError:
        return None


def resolve_title(parsed: Dict[str, Any], source_text: str) -> str:
    return normalized_text(parsed.get("title")) or source_text[:28]


def resolve_description(parsed: Dict[str, Any], source_text: str) -> str:
    description = normalized_text(parsed.get("description")) or source_text
    assumptions = normalized_text(parsed.get("assumptions"))
    if assumptions:
        return f"{description}\n\nAI 推断说明：{assumptions}"
    return description


def resolve_deadline(
    parsed: Dict[str, Any],
    fixed_deadline: Optional[datetime],
    now: datetime,
    source_text: str,
) -> datetime:
    deadline = (
        fixed_deadline
        or infer_relative_deadline(source_text, now)
        or parse_datetime_field(parsed.get("deadline"), "deadline")
    )
    if deadline <= now:
        raise ValueError("AI 推断出的 DDL 已经过期，请在描述里补充更明确的时间。")
    return deadline


def infer_relative_deadline(source_text: str, now: datetime) -> Optional[datetime]:
    text = normalized_text(source_text)
    if not text:
        return None

    day_offset = infer_relative_day_offset(text)
    explicit_time = infer_explicit_time(text)
    if day_offset is None and explicit_time is None:
        return None

    if day_offset is None:
        day_offset = 0
    hour, minute = explicit_time or infer_default_deadline_time(text)
    deadline = (now + timedelta(days=day_offset)).replace(
        hour=hour,
        minute=minute,
        second=0,
        microsecond=0,
    )
    while deadline <= now:
        deadline += timedelta(days=1)
    return deadline


def infer_fixed_time_window(source_text: str, now: datetime) -> Optional[tuple[datetime, datetime]]:
    text = normalized_text(source_text)
    if not text or not looks_like_fixed_window_task(text):
        return None

    numeric_match = re.search(
        r"(?P<start_hour>\d{1,2})(?:\s*[:：点]\s*(?P<start_minute>\d{1,2}))?"
        r"\s*(?:-|~|～|到|至|—|－)\s*"
        r"(?P<end_hour>\d{1,2})(?:\s*[:：点]\s*(?P<end_minute>\d{1,2}))?\s*(?:点|分)?",
        text,
    )
    chinese_match = re.search(
        r"(?P<start_hour>[零〇一二两三四五六七八九十]{1,4})(?:\s*点\s*(?P<start_half>半)?)?"
        r"\s*(?:-|~|～|到|至|—|－)\s*"
        r"(?P<end_hour>[零〇一二两三四五六七八九十]{1,4})(?:\s*点\s*(?P<end_half>半)?)?",
        text,
    )
    if numeric_match:
        start_hour = int(numeric_match.group("start_hour"))
        start_minute = int(numeric_match.group("start_minute") or 0)
        end_hour = int(numeric_match.group("end_hour"))
        end_minute = int(numeric_match.group("end_minute") or 0)
    elif chinese_match:
        parsed_start_hour = parse_chinese_number(chinese_match.group("start_hour"))
        parsed_end_hour = parse_chinese_number(chinese_match.group("end_hour"))
        if parsed_start_hour is None or parsed_end_hour is None:
            return None
        start_hour = parsed_start_hour
        start_minute = 30 if chinese_match.group("start_half") else 0
        end_hour = parsed_end_hour
        end_minute = 30 if chinese_match.group("end_half") else 0
    else:
        return None

    start_time = normalize_time_of_day(
        hour=start_hour,
        minute=start_minute,
        text=text,
    )
    end_time = normalize_time_of_day(
        hour=end_hour,
        minute=end_minute,
        text=text,
    )
    if start_time is None or end_time is None:
        return None

    day_offset = infer_relative_day_offset(text)
    base = now + timedelta(days=day_offset or 0)
    start = base.replace(hour=start_time[0], minute=start_time[1], second=0, microsecond=0)
    end = base.replace(hour=end_time[0], minute=end_time[1], second=0, microsecond=0)
    if end <= start:
        end += timedelta(days=1)
    if end <= now:
        start += timedelta(days=1)
        end += timedelta(days=1)
    return start, end


def looks_like_fixed_window_task(text: str) -> bool:
    fixed_tokens = (
        "开会",
        "会议",
        "上课",
        "考试",
        "测验",
        "实验",
        "面试",
        "预约",
        "讲座",
        "值班",
        "活动",
        "从",
        "期间",
    )
    range_tokens = ("到", "至", "-", "~", "～", "—", "－")
    return any(token in text for token in fixed_tokens) and any(token in text for token in range_tokens)


def infer_relative_day_offset(text: str) -> Optional[int]:
    if "大后天" in text:
        return 3
    if "后天" in text:
        return 2
    if any(keyword in text for keyword in ("明天", "明早", "明晚", "明日上午", "明天下午", "明日")):
        return 1
    if any(keyword in text for keyword in ("今天", "今晚", "今夜", "早上", "上午")):
        return 0
    if any(keyword in text for keyword in ("上午", "中午", "下午", "晚上", "傍晚", "夜里")):
        return 0
    return None


def infer_default_deadline_time(text: str) -> tuple[int, int]:
    if any(keyword in text for keyword in ("今晚", "晚上", "傍晚", "夜里", "今夜")):
        return (23, 59)
    return (23, 59)


def infer_explicit_time(text: str) -> Optional[tuple[int, int]]:
    numeric_colon_match = re.search(r"(?P<hour>\d{1,2})\s*[:：]\s*(?P<minute>\d{1,2})", text)
    if numeric_colon_match:
        return normalize_time_of_day(
            hour=int(numeric_colon_match.group("hour")),
            minute=int(numeric_colon_match.group("minute")),
            text=text,
        )

    numeric_point_match = re.search(
        r"(?P<hour>\d{1,2})\s*[点點]\s*(?P<half>半)?\s*(?P<minute>\d{1,2})?\s*(?:分)?",
        text,
    )
    if numeric_point_match:
        minute = 30 if numeric_point_match.group("half") else int(numeric_point_match.group("minute") or 0)
        return normalize_time_of_day(
            hour=int(numeric_point_match.group("hour")),
            minute=minute,
            text=text,
        )

    chinese_point_match = re.search(
        r"(?P<hour>[零〇一二两三四五六七八九十]{1,4})\s*[点點]\s*(?P<half>半)?\s*(?P<minute>[零〇一二两三四五六七八九十]{1,4})?\s*(?:分)?",
        text,
    )
    if chinese_point_match:
        hour = parse_chinese_number(chinese_point_match.group("hour"))
        minute = 30 if chinese_point_match.group("half") else parse_chinese_number(chinese_point_match.group("minute") or "零")
        if hour is None or minute is None:
            return None
        return normalize_time_of_day(hour=hour, minute=minute, text=text)

    return None


def normalize_time_of_day(hour: int, minute: int, text: str) -> Optional[tuple[int, int]]:
    if minute < 0 or minute > 59:
        return None
    if is_afternoon_or_evening(text) and 1 <= hour <= 11:
        hour += 12
    if "中午" in text and 1 <= hour <= 10:
        hour += 12
    if hour < 0 or hour > 23:
        return None
    return (hour, minute)


def is_afternoon_or_evening(text: str) -> bool:
    return any(keyword in text for keyword in ("下午", "晚上", "今晚", "傍晚", "夜里", "今夜"))


def parse_chinese_number(value: str) -> Optional[int]:
    digits = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    if not value:
        return None
    if value in digits:
        return digits[value]
    if value == "十":
        return 10
    if "十" in value:
        left, right = value.split("十", 1)
        tens = digits.get(left, 1) if left else 1
        ones = digits.get(right, 0) if right else 0
        return tens * 10 + ones
    return None


def resolve_earliest_start(parsed: Dict[str, Any], now: datetime, deadline: datetime) -> datetime:
    earliest_start = parse_optional_datetime_field(parsed.get("earliest_start"))
    if earliest_start is None or earliest_start < now or earliest_start >= deadline:
        return now
    return earliest_start


def normalize_dependencies(value: Any, task_id_map: Dict[str, str]) -> tuple[str, ...]:
    valid_dependency_ids = existing_task_ids() | set(task_id_map.values())
    normalized_dependencies = []
    for dep in normalize_string_list(value):
        mapped_dep = task_id_map.get(dep, dep)
        if mapped_dep in valid_dependency_ids:
            normalized_dependencies.append(mapped_dep)
    return tuple(dict.fromkeys(normalized_dependencies))


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


def normalize_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    raw = normalized_text(value).lower()
    if raw in {"true", "1", "yes", "y", "是", "需要", "整块"}:
        return True
    if raw in {"false", "0", "no", "n", "否", "不需要", "可中断"}:
        return False
    return default


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


def deadline_type_clarification(task_request: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "task_text": task_request["task_text"],
        "fixed_deadline": task_request.get("fixed_deadline"),
        "summary": task_request["task_text"][:40],
        "questions": [
            {
                "id": "deadline_type",
                "prompt": "这个 DDL 是严格截止，还是你自己设定的期望完成时间？",
                "hint": "严格截止超时后直接标记超时；期望截止超时后进入未安排，可手动调整。",
                "required": True,
                "kind": "deadline_type",
            }
        ],
        "missing_aspects": ["deadline_type"],
        "confidence": 1.0,
    }


def with_deadline_type_question(
    task_request: Dict[str, Any],
    pending: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    deadline_pending = deadline_type_clarification(task_request)
    if pending is None:
        return deadline_pending
    questions = list(pending.get("questions", []))
    if not any(str(question.get("id")) == "deadline_type" for question in questions):
        questions.append(deadline_pending["questions"][0])
    return {
        **pending,
        "questions": questions[:4],
        "missing_aspects": list(pending.get("missing_aspects", [])) + ["deadline_type"],
    }


def infer_deadline_type(text: str) -> Optional[DeadlineType]:
    normalized = normalized_text(text)
    strict_tokens = (
        "必须",
        "一定要",
        "提交",
        "考试",
        "测验",
        "上课",
        "会议",
        "预约",
        "面试",
        "不能晚",
        "不能超过",
        "不可补救",
        "过了就",
        "过期",
        "硬性",
        "严格",
    )
    flexible_tokens = (
        "希望",
        "最好",
        "尽量",
        "计划",
        "期望",
        "想在",
        "自己定",
        "自定",
        "不急",
        "可以晚",
    )
    if any(token in normalized.lower() for token in strict_tokens):
        return DeadlineType.STRICT
    if any(token in normalized.lower() for token in flexible_tokens):
        return DeadlineType.FLEXIBLE
    return None


def normalize_deadline_type(value: Any) -> DeadlineType:
    if isinstance(value, DeadlineType):
        return value
    raw = normalized_text(value).lower()
    aliases = {
        "strict": DeadlineType.STRICT,
        "hard": DeadlineType.STRICT,
        "严格": DeadlineType.STRICT,
        "严格截止": DeadlineType.STRICT,
        "flexible": DeadlineType.FLEXIBLE,
        "soft": DeadlineType.FLEXIBLE,
        "期望": DeadlineType.FLEXIBLE,
        "期望截止": DeadlineType.FLEXIBLE,
    }
    return aliases.get(raw, DeadlineType.FLEXIBLE)


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


def record_added_tasks(task_payloads: List[Dict[str, Any]]) -> None:
    for task_payload in task_payloads:
        record_operation(
            "task_added",
            task_id=str(task_payload["task_id"]),
            title=str(task_payload["title"]),
            detail=f"duration_min={task_payload['duration_min']}",
        )


def show_task_added_message(task_payloads: List[Dict[str, Any]]) -> None:
    if len(task_payloads) == 1:
        st.session_state.task_added_notice = single_task_notice(task_payloads[0])
        return
    st.session_state.task_added_notice = f"AI 已拆解并添加 {len(task_payloads)} 个任务。"


def single_task_notice(task_payload: Dict[str, Any]) -> str:
    deadline = datetime.fromisoformat(task_payload["deadline"])
    return (
        f"AI 已添加任务：{task_payload['title']} · "
        f"{task_payload['duration_min']} 分钟 · DDL {deadline:%m-%d %H:%M}"
    )
