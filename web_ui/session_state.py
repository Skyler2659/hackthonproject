from __future__ import annotations

from datetime import time

import streamlit as st

from web_ui.constants import DEFAULT_BASE_URL


def init_session_state() -> None:
    defaults = {
        "pending_tasks": [],
        "last_scores": None,
        "last_result": None,
        "last_ordered_tasks": None,
        "last_profile": None,
        "last_run_at": None,
        "auto_schedule_needed": False,
        "profile_config": {},
        "api_key": "",
        "llm_model": "deepseek-chat",
        "llm_base_url": DEFAULT_BASE_URL,
        "ensemble_size": 3,
        "energy_peak": "Morning",
        "max_daily_deep_work_min": 180,
        "preferred_environments": ["desk", "library"],
        "use_morning_window": True,
        "morning_start": time(8, 30),
        "morning_end": time(12, 0),
        "use_afternoon_window": True,
        "afternoon_start": time(14, 0),
        "afternoon_end": time(17, 30),
        "use_night_window": True,
        "night_start": time(19, 0),
        "night_end": time(22, 0),
        "quiet_start": time(9, 0),
        "quiet_end": time(11, 30),
        "weight_lateness": 3.0,
        "weight_cognitive_fit": 1.4,
        "weight_context_switch": 0.7,
        "weight_fragmentation": 0.8,
        "weight_preference_match": 1.0,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def clear_last_run() -> None:
    st.session_state.last_scores = None
    st.session_state.last_result = None
    st.session_state.last_ordered_tasks = None
    st.session_state.last_profile = None
    st.session_state.last_run_at = None


def mark_schedule_dirty() -> None:
    clear_last_run()
    st.session_state.auto_schedule_needed = True

