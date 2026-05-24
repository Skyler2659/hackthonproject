from __future__ import annotations

from typing import Any, Dict, List

import streamlit as st

from agents import TaskClarificationAgent
from llm_client import LLMProviderError
from web_ui.profile import build_profile
from web_ui.styles import styled_warning, styled_error
from web_ui.task_data import materialize_tasks


def render_task_clarification_dialog(profile_config: Dict[str, Any]) -> None:
    pending = st.session_state.get("task_clarification_pending")
    if not pending:
        return
    config = st.session_state.get("profile_config") or profile_config
    if hasattr(st, "dialog"):
        @st.dialog("补充一点任务细节")
        def _dialog() -> None:
            render_clarification_panel(config)

        _dialog()
    else:
        render_clarification_panel(config)


def render_clarification_panel(profile_config: Dict[str, Any]) -> None:
    pending = st.session_state.get("task_clarification_pending")
    if not pending:
        return

    st.info("AI 觉得这条描述还不够具体，补充几句后排程会更准。")
    st.markdown(f"**已理解：** {pending.get('summary', pending.get('task_text', ''))}")

    answers = render_clarification_form(pending.get("questions", []))
    submit_col, skip_col = st.columns(2)
    if submit_col.button("补充并添加任务", type="primary", use_container_width=True):
        submit_clarification(pending, answers, profile_config, skip=False)
    if skip_col.button("跳过，按 AI 推断", use_container_width=True):
        submit_clarification(pending, answers, profile_config, skip=True)


def render_clarification_form(questions: List[Dict[str, Any]]) -> Dict[str, str]:
    answers: Dict[str, str] = {}
    for question in questions:
        question_id = str(question.get("id", ""))
        label = str(question.get("prompt", "补充说明"))
        if question.get("required"):
            label = f"{label} *"
        if question.get("kind") == "deadline_type" or question_id == "deadline_type":
            label_by_value = {
                "strict": "严格截止：超时后不能补救，直接标记超时",
                "flexible": "期望截止：超时后还能补救，进入未安排",
            }
            selected = st.radio(
                label,
                options=["flexible", "strict"],
                format_func=lambda value: label_by_value[value],
                key=f"task_clarify_{question_id}",
            )
            answers[question_id] = selected
            if question.get("hint"):
                st.caption(str(question.get("hint")))
            continue
        answers[question_id] = st.text_input(
            label,
            placeholder=str(question.get("hint") or ""),
            key=f"task_clarify_{question_id}",
        )
    return answers


def submit_clarification(
    pending: Dict[str, Any],
    answers: Dict[str, str],
    profile_config: Dict[str, Any],
    *,
    skip: bool,
) -> None:
    if not skip:
        missing_required = [
            str(question.get("prompt", question.get("id")))
            for question in pending.get("questions", [])
            if question.get("required") and not str(answers.get(str(question.get("id")), "")).strip()
        ]
        if missing_required:
            styled_warning("请先回答标有 * 的问题，或点「跳过，按 AI 推断」。")
            return

    enriched_text = pending["task_text"]
    if not skip:
        enriched_text = TaskClarificationAgent.merge_user_answers(
            pending["task_text"],
            pending.get("questions", []),
            answers,
        )

    clear_clarification_pending()
    task_request = {
        "task_text": enriched_text,
        "fixed_deadline": pending.get("fixed_deadline"),
        "_skip_clarification": True,
    }
    if str(answers.get("deadline_type", "")).strip():
        task_request["_deadline_type"] = str(answers["deadline_type"]).strip()
    from web_ui.task_input import create_task_payloads, finalize_added_tasks, validate_task_request

    validation_error = validate_task_request(task_request, profile_config)
    if validation_error:
        styled_warning(validation_error)
        return

    try:
        task_payloads = create_task_payloads(task_request, profile_config)
    except LLMProviderError as exc:
        styled_error(f"AI 任务分析失败：{exc}")
        return
    except ValueError as exc:
        styled_error(f"AI 解析结果不合法：{exc}")
        return
    except Exception as exc:  # pragma: no cover
        styled_error(f"任务分析失败：{type(exc).__name__}: {exc}")
        return

    finalize_added_tasks(task_payloads)
    st.rerun()


def assess_task_clarification(
    task_request: Dict[str, Any],
    profile_config: Dict[str, Any],
) -> Dict[str, Any] | None:
    """Return pending clarification dict, or None if can proceed directly."""
    if task_request.get("_skip_clarification"):
        return None

    from datetime import datetime

    now = datetime.now().replace(second=0, microsecond=0)
    profile = build_profile(profile_config)
    existing_tasks = materialize_tasks(st.session_state.pending_tasks)
    from web_ui.task_input import build_llm_client

    agent = TaskClarificationAgent(llm_client=build_llm_client(profile_config))
    try:
        with st.spinner("AI 正在判断是否需要补充信息..."):
            assessment = agent.assess(
                user_text=task_request["task_text"],
                profile=profile,
                now=now,
                existing_tasks=existing_tasks,
            )
    except LLMProviderError:
        from agents.task_clarification_agent import heuristic_assessment

        assessment = heuristic_assessment(task_request["task_text"])

    if not assessment.get("needs_clarification"):
        return None

    return {
        "task_text": task_request["task_text"],
        "fixed_deadline": task_request.get("fixed_deadline"),
        "summary": assessment.get("summary", ""),
        "questions": assessment.get("questions", []),
        "missing_aspects": assessment.get("missing_aspects", []),
        "confidence": assessment.get("confidence", 0.0),
    }


def start_clarification_pending(pending: Dict[str, Any]) -> None:
    st.session_state.task_clarification_pending = pending


def clear_clarification_pending() -> None:
    st.session_state.task_clarification_pending = None
