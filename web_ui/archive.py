from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import streamlit as st


ARCHIVE_PATH = Path(__file__).resolve().parents[1] / "data" / "scheduler_archive.json"
ARCHIVE_VERSION = 1
MAX_HISTORY_EVENTS = 500


def load_archive() -> Dict[str, Any]:
    if not ARCHIVE_PATH.exists():
        return empty_archive()
    try:
        with ARCHIVE_PATH.open("r", encoding="utf-8") as archive_file:
            archive = json.load(archive_file)
    except (OSError, json.JSONDecodeError):
        return empty_archive()
    return {
        "version": archive.get("version", ARCHIVE_VERSION),
        "pending_tasks": list(archive.get("pending_tasks", [])),
        "operation_history": list(archive.get("operation_history", []))[-MAX_HISTORY_EVENTS:],
    }


def empty_archive() -> Dict[str, Any]:
    return {
        "version": ARCHIVE_VERSION,
        "pending_tasks": [],
        "operation_history": [],
    }


def save_session_archive() -> None:
    ARCHIVE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": ARCHIVE_VERSION,
        "updated_at": datetime.now().replace(microsecond=0).isoformat(),
        "pending_tasks": json_safe(list(st.session_state.get("pending_tasks", []))),
        "operation_history": json_safe(
            list(st.session_state.get("operation_history", []))[-MAX_HISTORY_EVENTS:]
        ),
    }
    temp_path = ARCHIVE_PATH.with_suffix(".tmp")
    temp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    temp_path.replace(ARCHIVE_PATH)


def record_operation(
    event_type: str,
    task_id: str = "",
    title: str = "",
    detail: str = "",
) -> None:
    history: List[Dict[str, Any]] = list(st.session_state.get("operation_history", []))
    history.append(
        {
            "event_type": event_type,
            "task_id": task_id,
            "title": title,
            "detail": detail,
            "created_at": datetime.now().replace(microsecond=0).isoformat(),
        }
    )
    st.session_state.operation_history = history[-MAX_HISTORY_EVENTS:]
    save_session_archive()


def json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))
