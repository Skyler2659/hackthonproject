from __future__ import annotations

from typing import Any, Dict

import streamlit as st

from models import UserWeights
from web_ui.constants import DEFAULT_BASE_URL, ENVIRONMENT_OPTIONS
from web_ui.profile import build_available_windows, build_energy_curve


def render_sidebar() -> Dict[str, Any]:
    with st.sidebar:
        st.header("User Profile")
        llm_settings = render_llm_settings()
        profile_settings = render_profile_settings()
        available_windows = render_available_windows()
        quiet_windows = render_quiet_windows()
        weights = render_preference_weights()

    config = {
        **llm_settings,
        **profile_settings,
        "available_windows": available_windows,
        "quiet_windows": quiet_windows,
        "weights": weights,
    }
    st.session_state.profile_config = config
    return config


def render_llm_settings() -> Dict[str, Any]:
    api_key = st.text_input(
        "DeepSeek API Key",
        type="password",
        key="api_key",
        help="仅保存在当前 Streamlit 会话中，用于调用 AI 分析任务和生成日程。",
    )
    model = st.text_input("LLM Model", key="llm_model")
    base_url = st.text_input("LLM Base URL", key="llm_base_url")
    ensemble_size = st.slider("Agent Ensemble Size", 1, 5, key="ensemble_size")
    st.divider()
    return {
        "api_key": api_key.strip(),
        "model": model.strip() or "deepseek-chat",
        "base_url": base_url.strip() or DEFAULT_BASE_URL,
        "ensemble_size": int(ensemble_size),
    }


def render_profile_settings() -> Dict[str, Any]:
    energy_peak = st.selectbox(
        "精力高峰期",
        options=["Morning", "Afternoon", "Night", "Irregular"],
        key="energy_peak",
    )
    max_daily_deep_work_min = st.slider(
        "每日深度工作上限 (min)",
        30,
        360,
        step=15,
        key="max_daily_deep_work_min",
    )
    preferred_environments = st.multiselect(
        "偏好环境",
        ENVIRONMENT_OPTIONS,
        key="preferred_environments",
    )
    return {
        "energy_peak": energy_peak,
        "chronotype": energy_peak.lower(),
        "energy_curve": build_energy_curve(energy_peak),
        "max_daily_deep_work_min": int(max_daily_deep_work_min),
        "preferred_environments": tuple(preferred_environments or ["desk"]),
    }


def render_available_windows() -> tuple:
    with st.expander("可用时间窗", expanded=True):
        use_morning = st.checkbox("Morning Slot", key="use_morning_window")
        col_a, col_b = st.columns(2)
        morning_start = col_a.time_input("Morning Start", key="morning_start")
        morning_end = col_b.time_input("Morning End", key="morning_end")

        use_afternoon = st.checkbox("Afternoon Slot", key="use_afternoon_window")
        col_a, col_b = st.columns(2)
        afternoon_start = col_a.time_input("Afternoon Start", key="afternoon_start")
        afternoon_end = col_b.time_input("Afternoon End", key="afternoon_end")

        use_night = st.checkbox("Night Slot", key="use_night_window")
        col_a, col_b = st.columns(2)
        night_start = col_a.time_input("Night Start", key="night_start")
        night_end = col_b.time_input("Night End", key="night_end")

    return build_available_windows(
        [
            (use_morning, morning_start, morning_end),
            (use_afternoon, afternoon_start, afternoon_end),
            (use_night, night_start, night_end),
        ]
    )


def render_quiet_windows() -> tuple:
    with st.expander("安静专注窗口"):
        col_a, col_b = st.columns(2)
        quiet_start = col_a.time_input("Quiet Start", key="quiet_start")
        quiet_end = col_b.time_input("Quiet End", key="quiet_end")
    return tuple([(quiet_start, quiet_end)] if quiet_start < quiet_end else [])


def render_preference_weights() -> UserWeights:
    with st.expander("排程偏好设置"):
        lateness = render_lateness_weight()
        cognitive_fit = render_cognitive_fit_weight()
        context_switch = render_context_switch_weight()
        fragmentation = render_fragmentation_weight()
        preference_match = render_preference_match_weight()
    return UserWeights(
        lateness=float(lateness),
        cognitive_fit=float(cognitive_fit),
        context_switch=float(context_switch),
        fragmentation=float(fragmentation),
        preference_match=float(preference_match),
    )


def render_lateness_weight() -> float:
    value = st.slider(
        "更重视截止时间",
        0.0,
        6.0,
        step=0.1,
        key="weight_lateness",
        help="越高，越会优先安排临近 DDL 或延误代价高的任务。",
    )
    st.caption("调高后，系统会更积极地把快到期的任务排到前面。")
    return float(value)


def render_cognitive_fit_weight() -> float:
    value = st.slider(
        "更重视精力匹配",
        0.0,
        4.0,
        step=0.1,
        key="weight_cognitive_fit",
        help="越高，越会把高认知负荷任务放进高精力时段。",
    )
    st.caption("调高后，难任务更容易被安排在你的精力高峰期。")
    return float(value)


def render_context_switch_weight() -> float:
    value = st.slider(
        "更希望少切换任务",
        0.0,
        3.0,
        step=0.1,
        key="weight_context_switch",
        help="越高，越倾向于减少不同类型任务之间的频繁切换。",
    )
    st.caption("调高后，系统会更偏向把相近类型的任务安排得连续一些。")
    return float(value)


def render_fragmentation_weight() -> float:
    value = st.slider(
        "更希望保留完整时间块",
        0.0,
        3.0,
        step=0.1,
        key="weight_fragmentation",
        help="越高，越不喜欢把任务切得太碎。",
    )
    st.caption("调高后，深度工作任务会更倾向于获得连续的大块时间。")
    return float(value)


def render_preference_match_weight() -> float:
    value = st.slider(
        "更重视个人偏好",
        0.0,
        3.0,
        step=0.1,
        key="weight_preference_match",
        help="越高，越会照顾你设置的环境、安静时段和时间偏好。",
    )
    st.caption("调高后，排程会更贴近你的习惯；调低后，系统会更强调完成效率。")
    return float(value)

