from __future__ import annotations

from datetime import datetime, time
from typing import Any, Dict, Iterable, List

from models import ScheduleResult, TaskScore, UserProfile


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


def serialize_profile(profile: UserProfile | None) -> Dict[str, Any] | None:
    if profile is None:
        return None
    return {
        "user_id": profile.user_id,
        "chronotype": profile.chronotype,
        "energy_curve": {str(hour): energy for hour, energy in profile.energy_curve.items()},
        "available_windows": serialize_time_windows(profile.available_windows),
        "quiet_windows": serialize_time_windows(profile.quiet_windows),
        "preferred_windows": serialize_time_windows(profile.preferred_windows),
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


def serialize_time_windows(windows: Iterable[tuple[time, time]]) -> List[List[str]]:
    return [[start.strftime("%H:%M"), end.strftime("%H:%M")] for start, end in windows]


def parse_optional_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone().replace(tzinfo=None)
    return parsed.replace(second=0, microsecond=0)
