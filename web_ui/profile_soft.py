from __future__ import annotations

from dataclasses import replace
from datetime import time
from typing import Any, Dict

from models import UserProfile
from web_ui.profile import build_profile
from web_ui.user_memory import ENERGY_LABELS, ENVIRONMENT_LABELS_CN, format_windows

# Hard planning horizon for the solver (DDL / overlap / deps remain hard).
GENEROUS_SCHEDULING_WINDOWS = ((time(6, 0), time(23, 45)),)


def build_algorithm_profile(config: Dict[str, Any]) -> UserProfile:
    """Solver profile: wide day window; questionnaire windows only steer costs."""
    base = build_profile(config)
    preference = config.get("available_windows") or base.available_windows
    return replace(
        base,
        available_windows=GENEROUS_SCHEDULING_WINDOWS,
        preferred_windows=preference,
    )


def build_profile_soft_hints(memory: Dict[str, Any]) -> str:
    """Natural-language preference block for AI agents (not CP-SAT hard rules)."""
    answers = dict(memory.get("answers") or {})
    energy_peak = str(memory.get("energy_peak") or "Morning")
    lines = [
        "【用户画像软约束 — 供理解与微调参考，非绝对硬边界】",
        f"节奏名称：{memory.get('profile_name', '默认节奏')}",
        f"精力高峰：{ENERGY_LABELS.get(energy_peak, energy_peak)}（chronotype={energy_peak.lower()}）",
        f"偏好工作时段：{format_windows(memory.get('available_windows', []))}",
        f"偏好安静时段：{format_windows(memory.get('quiet_windows', []))}",
        f"每日深度专注预算约：{int(memory.get('max_daily_deep_work_min', 180))} 分钟（任务内 deep_work_min 累加，可适度超出）",
        f"偏好环境：{environment_hint(memory.get('preferred_environments', []))}",
    ]
    weights = memory.get("weights") or {}
    if weights:
        lines.append(
            "权重倾向："
            f"DDL压力{weights.get('lateness', 3):.1f}、"
            f"精力匹配{weights.get('cognitive_fit', 1.4):.1f}、"
            f"少切换{weights.get('context_switch', 0.7):.1f}、"
            f"整块时间{weights.get('fragmentation', 0.8):.1f}、"
            f"习惯匹配{weights.get('preference_match', 1.0):.1f}"
        )
    if answers:
        lines.append(f"问卷答案摘要：{summarize_answers(answers)}")
    lines.append(
        "调度时请优先满足任务 DDL、依赖、固定时段与互不重叠；"
        "画像时段/安静/深度预算用于打分与排程后微调，可在必要时适度放宽以塞进未排任务。"
    )
    return "\n".join(lines)


def environment_hint(environments: Any) -> str:
    if not environments:
        return "未特别限制"
    return "、".join(ENVIRONMENT_LABELS_CN.get(str(item), str(item)) for item in environments)


def summarize_answers(answers: Dict[str, Any]) -> str:
    labels = {
        "rhythm": {"sunrise": "晨型", "lunch": "午后型", "moon": "夜型", "weather": "不规律"},
        "day_shape": {"classic": "经典工位日", "split": "多段空档", "late": "偏晚启动", "compact": "紧凑日程"},
        "focus_noise": {"cave": "需要洞穴安静", "hum": "低噪即可", "flex": "弹性", "chaos": "嘈杂也可"},
        "deep_tank": {"sprint": "深度续航短", "movie": "中等", "chapter": "较长", "marathon": "很长"},
        "deadline_style": {"fire": "DDL极敏感", "steady": "稳健", "buffer": "留缓冲", "soft": "DDL较软"},
        "energy_match": {"strict": "严格精力匹配", "balanced": "平衡", "casual": "随意"},
        "switching": {"batch": "讨厌频繁切换", "mixed": "可接受", "shuffle": "习惯穿插"},
        "block_style": {"deep": "偏好长块", "medium": "中等", "snack": "碎片"},
        "preference_style": {"ritual": "固定仪式", "normal": "一般", "anywhere": "随处可做"},
    }
    parts = []
    for key, mapping in labels.items():
        value = answers.get(key)
        if value in mapping:
            parts.append(f"{key}={mapping[value]}")
    return "；".join(parts) if parts else str(answers)
