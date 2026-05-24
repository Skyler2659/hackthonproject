from __future__ import annotations

from datetime import datetime

import streamlit as st
from web_ui.auto_scheduler import render_auto_scheduler
from web_ui.auth import require_authentication
from web_ui.constants import APP_TITLE
from web_ui.onboarding import render_profile_onboarding
from web_ui.results import render_results
from web_ui.session_state import init_session_state
from web_ui.sidebar import render_sidebar
from web_ui.styles import inject_styles
from web_ui.task_data import mark_overdue_tasks_missed
from web_ui.task_edit import render_task_edit_panel
from web_ui.task_input import render_task_form
from web_ui.task_list import render_pending_tasks


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    inject_styles()
    if not require_authentication():
        return
    init_session_state()
    render_profile_onboarding()
    render_page_header()
    render_page_body()


def render_page_header() -> None:
    st.title("Chrona")
    st.caption("AI 语义评分 + 确定性调度")


def render_page_body() -> None:
    profile_config = render_sidebar()
    now = datetime.now().replace(second=0, microsecond=0)
    previous_scores = st.session_state.last_scores
    previous_profile = st.session_state.last_profile
    missed_task_ids = mark_overdue_tasks_missed(now)
    recover_after_miss(missed_task_ids, previous_scores, previous_profile, now)
    render_auto_scheduler(profile_config)
    render_results()
    render_task_edit_panel()
    render_pending_tasks()
    render_task_form(profile_config)


def recover_after_miss(missed_task_ids, scores, profile, now: datetime) -> None:
    if missed_task_ids:
        st.session_state.auto_schedule_needed = True


if __name__ == "__main__":
    main()
