from __future__ import annotations

import json
from datetime import datetime, time
from pathlib import Path
from typing import Any, Dict, List

import streamlit as st

from models import ScheduleBlock, ScheduleResult, TaskScore, UserProfile, UserWeights
from web_ui.auth import current_username, user_data_dir


LEGACY_ARCHIVE_PATH = Path(__file__).resolve().parents[1] / "data" / "session_archive.json"


def archive_path() -> Path:
    username = current_username()
    if not username:
        return LEGACY_ARCHIVE_PATH
    return user_data_dir(username) / "session_archive.json"


def load_archive() -> Dict[str, Any]:
    path = archive_path()
    if not path.exists():
        return empty_archive()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return empty_archive()
    return {
        "pending_tasks": list(payload.get("pending_tasks", [])),
        "operation_history": list(payload.get("operation_history", [])),
        "last_scores": deserialize_scores(payload.get("last_scores")),
        "last_result": deserialize_schedule_result(payload.get("last_result")),
        "last_profile": deserialize_profile(payload.get("last_profile")),
        "last_run_at": parse_optional_datetime(payload.get("last_run_at")),
    }


def empty_archive() -> Dict[str, Any]:
    return {
        "pending_tasks": [],
        "operation_history": [],
        "last_scores": None,
        "last_result": None,
        "last_profile": None,
        "last_run_at": None,
    }


def record_operation(
    operation: str,
    *,
    task_id: str = "",
    title: str = "",
    detail: str = "",
) -> None:
    st.session_state.setdefault("operation_history", [])
    st.session_state.operation_history.append(
        {
            "operation": operation,
            "task_id": task_id,
            "title": title,
            "detail": detail,
            "created_at": datetime.now().replace(microsecond=0).isoformat(),
        }
    )
    save_session_archive()


def save_session_archive() -> None:
    path = archive_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "pending_tasks": st.session_state.get("pending_tasks", []),
        "operation_history": st.session_state.get("operation_history", []),
        "last_scores": serialize_scores(st.session_state.get("last_scores")),
        "last_result": serialize_schedule_result(st.session_state.get("last_result")),
        "last_profile": serialize_profile(st.session_state.get("last_profile")),
        "last_run_at": serialize_datetime(st.session_state.get("last_run_at")),
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def serialize_schedule_result(result: ScheduleResult | None) -> Dict[str, Any] | None:
    if result is None:
        return None
    return {
        "blocks": [
            {
                "task_id": block.task_id,
                "title": block.title,
                "start": block.start.isoformat(),
                "end": block.end.isoformat(),
                "priority": block.priority,
                "reason": block.reason,
            }
            for block in result.blocks
        ],
        "unscheduled_task_ids": list(result.unscheduled_task_ids),
        "total_cost": result.total_cost,
    }


def deserialize_schedule_result(payload: Any) -> ScheduleResult | None:
    if not isinstance(payload, dict):
        return None
    try:
        blocks = [
            ScheduleBlock(
                task_id=str(block["task_id"]),
                title=str(block["title"]),
                start=datetime.fromisoformat(str(block["start"])),
                end=datetime.fromisoformat(str(block["end"])),
                priority=float(block["priority"]),
                reason=str(block.get("reason", "")),
            )
            for block in payload.get("blocks", [])
            if isinstance(block, dict)
        ]
        return ScheduleResult(
            blocks=blocks,
            unscheduled_task_ids=[str(task_id) for task_id in payload.get("unscheduled_task_ids", [])],
            total_cost=float(payload.get("total_cost", 0.0)),
        )
    except (KeyError, TypeError, ValueError):
        return None


def serialize_scores(scores: Dict[str, TaskScore] | None) -> Dict[str, Any] | None:
    if not scores:
        return None
    return {
        task_id: {
            "task_id": score.task_id,
            "urgency": score.urgency,
            "complexity": score.complexity,
            "cognitive_load": score.cognitive_load,
            "block_integrity": score.block_integrity,
            "quietness_need": score.quietness_need,
            "confidence": score.confidence,
            "rationale": score.rationale,
            "environment_dependency": score.environment_dependency,
            "agent_votes": list(score.agent_votes),
        }
        for task_id, score in scores.items()
    }


def deserialize_scores(payload: Any) -> Dict[str, TaskScore] | None:
    if not isinstance(payload, dict):
        return None
    scores: Dict[str, TaskScore] = {}
    for task_id, raw_score in payload.items():
        if not isinstance(raw_score, dict):
            continue
        try:
            scores[str(task_id)] = TaskScore(
                task_id=str(raw_score.get("task_id") or task_id),
                urgency=float(raw_score.get("urgency", 0.5)),
                complexity=float(raw_score.get("complexity", 0.5)),
                cognitive_load=float(raw_score.get("cognitive_load", 0.5)),
                block_integrity=float(raw_score.get("block_integrity", 0.5)),
                quietness_need=float(raw_score.get("quietness_need", 0.45)),
                confidence=float(raw_score.get("confidence", 0.5)),
                rationale=str(raw_score.get("rationale", "")),
                environment_dependency=float(raw_score.get("environment_dependency", 0.0)),
                agent_votes=list(raw_score.get("agent_votes", [])),
            ).normalized()
        except (TypeError, ValueError):
            continue
    return scores or None


def serialize_profile(profile: UserProfile | None) -> Dict[str, Any] | None:
    if profile is None:
        return None
    return {
        "user_id": profile.user_id,
        "chronotype": profile.chronotype,
        "energy_curve": {str(hour): energy for hour, energy in profile.energy_curve.items()},
        "available_windows": serialize_time_windows(profile.available_windows),
        "quiet_windows": serialize_time_windows(profile.quiet_windows),
        "max_daily_deep_work_min": profile.max_daily_deep_work_min,
        "preferred_environments": list(profile.preferred_environments),
        "weights": {
            "lateness": profile.weights.lateness,
            "cognitive_fit": profile.weights.cognitive_fit,
            "context_switch": profile.weights.context_switch,
            "fragmentation": profile.weights.fragmentation,
            "preference_match": profile.weights.preference_match,
        },
    }


def deserialize_profile(payload: Any) -> UserProfile | None:
    if not isinstance(payload, dict):
        return None
    try:
        weights_payload = payload.get("weights", {})
        weights = UserWeights(
            lateness=float(weights_payload.get("lateness", 3.0)),
            cognitive_fit=float(weights_payload.get("cognitive_fit", 1.4)),
            context_switch=float(weights_payload.get("context_switch", 0.7)),
            fragmentation=float(weights_payload.get("fragmentation", 0.8)),
            preference_match=float(weights_payload.get("preference_match", 1.0)),
        )
        energy_curve = {
            int(hour): float(energy)
            for hour, energy in dict(payload.get("energy_curve", {})).items()
        }
        return UserProfile(
            user_id=str(payload.get("user_id", "local-user")),
            chronotype=str(payload.get("chronotype", "morning")),
            energy_curve=energy_curve,
            available_windows=deserialize_time_windows(payload.get("available_windows")),
            quiet_windows=deserialize_time_windows(payload.get("quiet_windows")),
            max_daily_deep_work_min=int(payload.get("max_daily_deep_work_min", 180)),
            preferred_environments=tuple(str(item) for item in payload.get("preferred_environments", ("desk",))),
            weights=weights,
        )
    except (TypeError, ValueError):
        return None


def serialize_time_windows(windows: Any) -> List[List[str]]:
    return [[start.strftime("%H:%M"), end.strftime("%H:%M")] for start, end in windows]


def deserialize_time_windows(value: Any) -> tuple[tuple[time, time], ...]:
    if not isinstance(value, list):
        return tuple()
    windows = []
    for window in value:
        if not isinstance(window, (list, tuple)) or len(window) != 2:
            continue
        start = parse_time_value(window[0])
        end = parse_time_value(window[1])
        if start is not None and end is not None and start < end:
            windows.append((start, end))
    return tuple(windows)


def parse_time_value(value: Any) -> time | None:
    try:
        return time.fromisoformat(str(value))
    except ValueError:
        return None


def serialize_datetime(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    return None


def parse_optional_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None
