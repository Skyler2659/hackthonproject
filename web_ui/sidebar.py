from __future__ import annotations

from typing import Any, Dict

import streamlit as st

from web_ui.auth import render_user_menu
from web_ui.constants import DEFAULT_BASE_URL
from web_ui.user_memory import (
    ENERGY_LABELS,
    ENVIRONMENT_LABELS_CN,
    format_windows,
    profile_config_from_memory,
)


def render_sidebar() -> Dict[str, Any]:
    with st.sidebar:
        st.header("用户画像")
        render_theme_toggle()
        render_user_menu()
        llm_settings = render_llm_settings()
        profile_settings = render_profile_memory_card()

    config = {
        **llm_settings,
        **profile_settings,
    }
    st.session_state.profile_config = config
    return config


def render_theme_toggle() -> None:
    st.radio(
        "显示模式",
        options=["day", "night"],
        format_func=lambda value: "日间模式" if value == "day" else "夜间模式",
        horizontal=True,
        key="theme_mode",
        label_visibility="collapsed",
    )


def render_llm_settings() -> Dict[str, Any]:
    api_key = st.text_input(
        "DeepSeek API Key",
        type="password",
        key="api_key",
        help="只保存在当前 Streamlit 会话中，用于调用 AI 分析任务和生成日程。",
    )
    model = st.text_input("LLM 模型", key="llm_model")
    base_url = st.text_input("LLM Base URL", key="llm_base_url")
    ensemble_size = st.slider("Agent 集成数量", 1, 5, key="ensemble_size")
    st.divider()
    return {
        "api_key": api_key.strip(),
        "model": model.strip() or "deepseek-chat",
        "base_url": base_url.strip() or DEFAULT_BASE_URL,
        "ensemble_size": int(ensemble_size),
    }


def render_profile_memory_card() -> Dict[str, Any]:
    memory = st.session_state.get("profile_memory", {})
    config = profile_config_from_memory(memory)
    weights = config["weights"]
    st.markdown("#### 系统记住的生活节奏")
    st.caption("这些偏好来自小测试，作为 AI 理解与微调提示（软约束）；硬算法只保证不重叠、DDL 与依赖。")
    st.markdown(
        f"""
        <div class="profile-memory-card">
          <div class="profile-memory-title">{memory.get("profile_name", "默认节奏")}</div>
          <p><b>精力高峰</b>：{ENERGY_LABELS.get(config["energy_peak"], config["energy_peak"])}</p>
          <p><b>常用窗口</b>：{format_windows(memory.get("available_windows", []))}</p>
          <p><b>安静窗口</b>：{format_windows(memory.get("quiet_windows", []))}</p>
          <p><b>深度工作</b>：{config["max_daily_deep_work_min"]} 分钟/天</p>
          <p><b>偏好环境</b>：{environment_text(config["preferred_environments"])}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.expander("算法会怎样使用这些记忆"):
        st.write("硬约束：任务截止、依赖、固定时段、日程块互不重叠。")
        st.write("软约束：问卷时段/安静/深度预算 → 进入 AI 提示词与排程代价，排程后由 AI 微调密度与未排任务。")
        st.write(f"DDL 压力权重：{weights.lateness:.1f}")
        st.write(f"精力匹配权重：{weights.cognitive_fit:.1f}")
        st.write(f"少切换权重：{weights.context_switch:.1f}")
        st.write(f"整块时间权重：{weights.fragmentation:.1f}")
        st.write(f"个人习惯权重：{weights.preference_match:.1f}")
    if st.button("重做我的节奏小测试", use_container_width=True):
        st.session_state.show_profile_test = True
        st.session_state.onboarding_step = "survey"
        st.rerun()
    return config


def environment_text(environments: tuple[str, ...]) -> str:
    return "、".join(ENVIRONMENT_LABELS_CN.get(env, env) for env in environments) or "暂未设置"
