from __future__ import annotations

from datetime import datetime

import streamlit as st

from web_ui.auto_scheduler import render_auto_scheduler
from web_ui.constants import APP_TITLE
from web_ui.results import render_results
from web_ui.session_state import init_session_state
from web_ui.sidebar import render_sidebar
from web_ui.styles import inject_styles
from web_ui.task_data import mark_overdue_tasks_missed
from web_ui.task_input import render_task_form
from web_ui.task_list import render_pending_tasks


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    inject_styles()
    init_session_state()
    render_page_header()
    render_page_body()


def render_page_header() -> None:
    st.title("认知能耗自适应调度引擎 V2.0")
    st.caption("AI 语义评分 + 确定性调度引擎")


def render_page_body() -> None:
    profile_config = render_sidebar()
    mark_overdue_tasks_missed(datetime.now().replace(second=0, microsecond=0))
    render_pending_tasks()
    render_auto_scheduler(profile_config)
    render_results()
    render_task_form(profile_config)


if __name__ == "__main__":
    main()
