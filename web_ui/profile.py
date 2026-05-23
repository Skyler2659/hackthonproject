from __future__ import annotations

from datetime import time
from typing import Any, Dict, Iterable, List, Tuple

from models import UserProfile


def build_profile(config: Dict[str, Any]) -> UserProfile:
    return UserProfile(
        user_id="streamlit_user",
        chronotype=config["chronotype"],
        energy_curve=config["energy_curve"],
        available_windows=config["available_windows"],
        quiet_windows=config["quiet_windows"],
        max_daily_deep_work_min=config["max_daily_deep_work_min"],
        preferred_environments=config["preferred_environments"],
        weights=config["weights"],
    )


def build_available_windows(
    windows: Iterable[Tuple[bool, time, time]],
) -> Tuple[Tuple[time, time], ...]:
    valid: List[Tuple[time, time]] = []
    for enabled, start, end in windows:
        if enabled and start < end:
            valid.append((start, end))
    return tuple(valid)


def build_energy_curve(energy_peak: str) -> Dict[int, float]:
    curve = {hour: 0.42 for hour in range(24)}
    templates = {
        "Morning": {
            range(8, 12): 0.88,
            range(13, 18): 0.62,
            range(19, 22): 0.55,
        },
        "Afternoon": {
            range(8, 12): 0.58,
            range(13, 18): 0.86,
            range(19, 22): 0.62,
        },
        "Night": {
            range(8, 12): 0.48,
            range(13, 18): 0.62,
            range(19, 23): 0.88,
        },
        "Irregular": {
            range(8, 12): 0.65,
            range(13, 18): 0.67,
            range(19, 22): 0.65,
        },
    }
    for hours, value in templates[energy_peak].items():
        for hour in hours:
            curve[hour] = value
    return curve

