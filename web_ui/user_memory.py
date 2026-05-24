from __future__ import annotations

import json
from copy import deepcopy
from datetime import time
from pathlib import Path
from typing import Any, Dict, Iterable, Tuple

from models import UserWeights
from web_ui.auth import current_username, user_data_dir
from web_ui.profile import build_energy_curve


LEGACY_MEMORY_PATH = Path(__file__).resolve().parents[1] / "data" / "user_profile_memory.json"


def memory_path() -> Path:
    username = current_username()
    if not username:
        return LEGACY_MEMORY_PATH
    return user_data_dir(username) / "user_profile_memory.json"

DEFAULT_MEMORY: Dict[str, Any] = {
    "completed": False,
    "profile_name": "默认节奏",
    "energy_peak": "Morning",
    "max_daily_deep_work_min": 180,
    "preferred_environments": ["desk", "library"],
    "available_windows": [["08:30", "12:00"], ["14:00", "17:30"], ["19:00", "22:00"]],
    "quiet_windows": [["09:00", "11:30"]],
    "weights": {
        "lateness": 3.0,
        "cognitive_fit": 1.4,
        "context_switch": 0.7,
        "fragmentation": 0.8,
        "preference_match": 1.0,
    },
    "answers": {},
}

ENERGY_LABELS = {
    "Morning": "晨间清醒派",
    "Afternoon": "午后开机派",
    "Night": "夜色加成派",
    "Irregular": "随机灵感派",
}

ENVIRONMENT_LABELS_CN = {
    "desk": "书桌/固定工位",
    "library": "图书馆/安静空间",
    "classroom": "教室/线下场景",
    "meeting_room": "会议室/讨论空间",
    "mobile": "通勤路上也能处理",
    "online": "线上工具/电脑环境",
}


def load_profile_memory() -> Dict[str, Any]:
    path = memory_path()
    if not path.exists():
        return deepcopy(DEFAULT_MEMORY)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return deepcopy(DEFAULT_MEMORY)
    memory = deepcopy(DEFAULT_MEMORY)
    memory.update({key: value for key, value in payload.items() if key in memory})
    memory["weights"] = {**DEFAULT_MEMORY["weights"], **dict(payload.get("weights", {}))}
    memory["answers"] = dict(payload.get("answers", {}))
    return memory


def save_profile_memory(memory: Dict[str, Any]) -> None:
    path = memory_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(memory, ensure_ascii=False, indent=2), encoding="utf-8")


def default_profile_memory(*, completed: bool = True) -> Dict[str, Any]:
    memory = deepcopy(DEFAULT_MEMORY)
    memory["completed"] = completed
    memory["profile_name"] = "先按默认节奏观察我"
    return memory


def profile_config_from_memory(memory: Dict[str, Any]) -> Dict[str, Any]:
    energy_peak = str(memory.get("energy_peak") or "Morning")
    return {
        "energy_peak": energy_peak,
        "chronotype": energy_peak.lower(),
        "energy_curve": build_energy_curve(energy_peak),
        "max_daily_deep_work_min": int(memory.get("max_daily_deep_work_min", 180)),
        "preferred_environments": tuple(memory.get("preferred_environments") or ["desk"]),
        "available_windows": parse_windows(memory.get("available_windows", [])),
        "quiet_windows": parse_windows(memory.get("quiet_windows", [])),
        "weights": weights_from_memory(memory),
    }


def weights_from_memory(memory: Dict[str, Any]) -> UserWeights:
    weights = {**DEFAULT_MEMORY["weights"], **dict(memory.get("weights", {}))}
    return UserWeights(
        lateness=float(weights["lateness"]),
        cognitive_fit=float(weights["cognitive_fit"]),
        context_switch=float(weights["context_switch"]),
        fragmentation=float(weights["fragmentation"]),
        preference_match=float(weights["preference_match"]),
    )


def parse_windows(raw_windows: Iterable[Iterable[str]]) -> Tuple[Tuple[time, time], ...]:
    windows = []
    for raw_window in raw_windows:
        try:
            start_raw, end_raw = list(raw_window)[:2]
            start = parse_time(start_raw)
            end = parse_time(end_raw)
        except (TypeError, ValueError):
            continue
        if start < end:
            windows.append((start, end))
    return tuple(windows)


def parse_time(value: str) -> time:
    hour, minute = str(value).split(":", 1)
    return time(int(hour), int(minute))


def format_windows(windows: Iterable[Iterable[str]]) -> str:
    formatted = [f"{start}-{end}" for start, end in windows]
    return "、".join(formatted) or "暂未设置"


def build_memory_from_answers(answers: Dict[str, Any]) -> Dict[str, Any]:
    energy_peak = rhythm_to_energy_peak(answers["rhythm"])
    available_windows = availability_windows(answers["day_shape"])
    quiet_windows = quiet_window(answers["focus_noise"])
    weights = answer_weights(answers)
    environments = list(answers.get("environments") or ["desk"])
    memory = {
        "completed": True,
        "profile_name": profile_name(answers),
        "energy_peak": energy_peak,
        "max_daily_deep_work_min": deep_work_limit(answers["deep_tank"]),
        "preferred_environments": environments,
        "available_windows": available_windows,
        "quiet_windows": quiet_windows,
        "weights": weights,
        "answers": answers,
    }
    return memory


def rhythm_to_energy_peak(answer: str) -> str:
    return {
        "sunrise": "Morning",
        "lunch": "Afternoon",
        "moon": "Night",
        "weather": "Irregular",
    }.get(answer, "Morning")


def availability_windows(answer: str) -> list[list[str]]:
    return {
        "classic": [["08:30", "12:00"], ["14:00", "17:30"]],
        "split": [["09:00", "11:30"], ["15:00", "18:00"], ["20:00", "22:30"]],
        "late": [["10:30", "13:00"], ["15:00", "18:30"], ["20:30", "23:30"]],
        "compact": [["09:30", "12:00"], ["14:30", "17:00"]],
    }.get(answer, DEFAULT_MEMORY["available_windows"])


def quiet_window(answer: str) -> list[list[str]]:
    return {
        "cave": [["09:00", "11:30"], ["14:30", "16:30"]],
        "hum": [["10:00", "12:00"]],
        "flex": [["15:00", "17:00"]],
        "chaos": [],
    }.get(answer, DEFAULT_MEMORY["quiet_windows"])


def deep_work_limit(answer: str) -> int:
    return {
        "sprint": 90,
        "movie": 150,
        "chapter": 210,
        "marathon": 300,
    }.get(answer, 180)


def answer_weights(answers: Dict[str, Any]) -> Dict[str, float]:
    deadline = answers["deadline_style"]
    energy = answers["energy_match"]
    switching = answers["switching"]
    block = answers["block_style"]
    preference = answers["preference_style"]
    return {
        "lateness": {"fire": 4.8, "steady": 3.4, "buffer": 4.0, "soft": 2.3}[deadline],
        "cognitive_fit": {"strict": 2.4, "balanced": 1.5, "casual": 0.8}[energy],
        "context_switch": {"batch": 2.3, "mixed": 1.1, "shuffle": 0.4}[switching],
        "fragmentation": {"deep": 2.4, "medium": 1.2, "snack": 0.5}[block],
        "preference_match": {"ritual": 2.1, "normal": 1.1, "anywhere": 0.5}[preference],
    }


def profile_name(answers: Dict[str, Any]) -> str:
    rhythm = {
        "sunrise": "晨光启动",
        "lunch": "午后升温",
        "moon": "夜间发力",
        "weather": "灵活漂移",
    }.get(answers["rhythm"], "自适应")
    block = {
        "deep": "整块专注",
        "medium": "稳态推进",
        "snack": "碎片快跑",
    }.get(answers["block_style"], "稳态推进")
    return f"{rhythm} · {block}"
