from __future__ import annotations

from datetime import time
from typing import Any, Dict, Iterable, Tuple

from models import UserProfile, UserWeights


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

GENEROUS_SCHEDULING_WINDOWS = ((time(6, 0), time(23, 45)),)


def build_user_profile(memory: Dict[str, Any], *, user_id: str, generous: bool = False) -> UserProfile:
    config = profile_config_from_memory(memory)
    windows = GENEROUS_SCHEDULING_WINDOWS if generous else config["available_windows"]
    return UserProfile(
        user_id=user_id,
        chronotype=config["chronotype"],
        energy_curve=config["energy_curve"],
        available_windows=windows,
        quiet_windows=config["quiet_windows"],
        preferred_windows=config["available_windows"],
        max_daily_deep_work_min=config["max_daily_deep_work_min"],
        preferred_environments=config["preferred_environments"],
        weights=config["weights"],
    )


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
    for hours, value in templates.get(energy_peak, templates["Morning"]).items():
        for hour in hours:
            curve[hour] = value
    return curve


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


def build_profile_soft_hints(memory: Dict[str, Any]) -> str:
    energy_peak = str(memory.get("energy_peak") or "Morning")
    weights = dict(memory.get("weights") or {})
    lines = [
        "【用户画像软约束 - 供理解与微调参考，非绝对硬边界】",
        f"节奏名称：{memory.get('profile_name', '默认节奏')}",
        f"精力高峰：{ENERGY_LABELS.get(energy_peak, energy_peak)}（chronotype={energy_peak.lower()}）",
        f"偏好工作时段：{format_windows(memory.get('available_windows', []))}",
        f"偏好安静时段：{format_windows(memory.get('quiet_windows', []))}",
        f"每日深度专注预算约：{int(memory.get('max_daily_deep_work_min', 180))} 分钟",
        f"偏好环境：{environment_hint(memory.get('preferred_environments', []))}",
    ]
    if weights:
        lines.append(
            "权重倾向："
            f"DDL压力{float(weights.get('lateness', 3.0)):.1f}、"
            f"精力匹配{float(weights.get('cognitive_fit', 1.4)):.1f}、"
            f"少切换{float(weights.get('context_switch', 0.7)):.1f}、"
            f"整块时间{float(weights.get('fragmentation', 0.8)):.1f}、"
            f"习惯匹配{float(weights.get('preference_match', 1.0)):.1f}"
        )
    lines.append("调度优先满足 DDL、依赖、固定时段与互不重叠；画像用于打分与排程后微调。")
    return "\n".join(lines)


def format_windows(windows: Iterable[Iterable[str]]) -> str:
    formatted = [f"{start}-{end}" for start, end in windows]
    return "、".join(formatted) or "暂未设置"


def environment_hint(environments: Any) -> str:
    if not environments:
        return "未特别限制"
    return "、".join(ENVIRONMENT_LABELS_CN.get(str(item), str(item)) for item in environments)
