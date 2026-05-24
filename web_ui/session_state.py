from __future__ import annotations

from datetime import time

import streamlit as st

from web_ui.constants import DEFAULT_BASE_URL
from web_ui.archive import load_archive, save_session_archive
from web_ui.user_memory import load_profile_memory


def init_session_state() -> None:
    archive = load_archive()
    profile_memory = load_profile_memory()
    defaults = {
        "pending_tasks": archive["pending_tasks"],
        "operation_history": archive["operation_history"],
        "task_added_notice": "",
        "task_clarification_pending": None,
        "last_scores": archive["last_scores"],
        "last_result": archive["last_result"],
        "last_ordered_tasks": None,
        "last_profile": archive["last_profile"],
        "last_run_at": archive["last_run_at"],
        "auto_schedule_needed": archive["last_result"] is None and bool(archive["pending_tasks"]),
        "profile_config": {},
        "profile_memory": profile_memory,
        "onboarding_step": "intro",
        "show_profile_test": not bool(profile_memory.get("completed")),
        "calendar_edit_mode": False,
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
    save_session_archive()
