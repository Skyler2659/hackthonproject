from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from llm.base import ReplayGuard


class MockLLMClient(ReplayGuard):
    """Deterministic local fallback for tests and offline demos.

    Routes to parser or scorer heuristics based on payload shape so UI
    developers can work fully offline without KeyErrors.
    """

    def __init__(self) -> None:
        super().__init__()
        self._response_cache: Dict[str, Dict[str, Any]] = {}

    def generate_json(
        self,
        system_prompt: str,
        payload: Dict[str, Any],
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        fingerprint = self.guard(system_prompt, payload, idempotency_key)
        if fingerprint not in self._response_cache:
            self._response_cache[fingerprint] = _route_and_generate(payload, fingerprint)
        return dict(self._response_cache[fingerprint])


# ── Routing ────────────────────────────────────────────────────────────

def _route_and_generate(payload: Dict[str, Any], fingerprint: str) -> Dict[str, Any]:
    """Inspect payload to decide parser vs scorer path."""
    if payload.get("mode") == "task_clarification":
        return _mock_clarify(payload, fingerprint)
    if payload.get("mode") == "schedule_refinement":
        return _mock_schedule_refinement(payload)
    if payload.get("mode") == "force_placement":
        return _mock_force_placement(payload)
    if "user_text" in payload:
        return _mock_parse(payload, fingerprint)
    return _mock_score(payload, fingerprint)


def _mock_force_placement(payload: Dict[str, Any]) -> Dict[str, Any]:
    task = payload.get("task") or {}
    candidates = list(payload.get("candidates") or [])
    if not candidates:
        return {"task_id": task.get("task_id", ""), "chosen_slot_id": "", "reason": "无候选时段"}
    ranked = sorted(
        candidates,
        key=lambda item: (
            min(item.get("gap_before_min", 0), item.get("gap_after_min", 0)),
            -float(item.get("heuristic_score", 0)),
        ),
        reverse=True,
    )
    chosen = ranked[0]
    return {
        "task_id": task.get("task_id", ""),
        "chosen_slot_id": chosen.get("slot_id", ""),
        "reason": "离线规则：优先前后留白较大的时段",
    }


def _mock_schedule_refinement(payload: Dict[str, Any]) -> Dict[str, Any]:
    unscheduled = list(payload.get("unscheduled_task_ids") or [])
    blocks = payload.get("scheduled_blocks") or []
    density = "balanced"
    if len(blocks) >= 2:
        from datetime import datetime

        ordered = sorted(blocks, key=lambda item: item["start"])
        gaps = []
        for index in range(len(ordered) - 1):
            left_end = datetime.fromisoformat(ordered[index]["end"])
            right_start = datetime.fromisoformat(ordered[index + 1]["start"])
            gaps.append((right_start - left_end).total_seconds() / 60)
        if gaps and min(gaps) < 10:
            density = "too_dense"
    leave = [
        {"task_id": task_id, "reason": "求解器未找到可行空档，请手动调整截止日或时长"}
        for task_id in unscheduled
    ]
    return {
        "density": density,
        "block_adjustments": [],
        "retry_unscheduled": unscheduled,
        "leave_unscheduled": leave,
        "summary": "离线规则检查完成，已尝试以适度强度塞入未排任务。",
    }


def _mock_clarify(payload: Dict[str, Any], fingerprint: str) -> Dict[str, Any]:
    from agents.task_clarification_agent import heuristic_assessment

    user_text = str(payload.get("user_text", ""))
    result = heuristic_assessment(user_text)
    if "高数" in user_text and "作业" in user_text:
        result = {
            "needs_clarification": True,
            "summary": "今晚完成高数作业，23:59 前截止",
            "missing_aspects": ["scope", "duration"],
            "questions": [
                {
                    "id": "scope",
                    "prompt": "这次高数作业具体要做哪些部分？",
                    "hint": "例如：第3章习题 1-10、两道证明题",
                    "required": True,
                },
                {
                    "id": "duration",
                    "prompt": "你预计大概需要多长时间？",
                    "hint": "例如：90分钟、大概两小时",
                    "required": True,
                },
            ],
            "confidence": 0.48,
        }
    return result


# ═══════════════════════════════════════════════════════════════════════════
#  Parser
# ═══════════════════════════════════════════════════════════════════════════

# ── Keyword tables ──────────────────────────────────────────────────────

_DEEP_WORK_ZH = (
    "报告", "论文", "代码", "编程", "研究", "设计", "分析", "写作",
    "算法", "数学", "架构", "文档", "方案", "规划", "深度工作",
)
_DEEP_WORK_EN = (
    "report", "paper", "code", "program", "research", "design",
    "analysis", "architecture", "algorithm", "math", "writing",
    "document", "proposal", "deep work",
)
_SHALLOW_ZH = ("邮件", "回复", "消息", "打卡", "填表", "会议", "聊天", "通知")
_SHALLOW_EN = ("email", "reply", "message", "check", "meeting", "chat")

_HIGH_QUIET_ZH = ("安静", "图书馆", "专注", "不打扰", "隔音", "静音")
_HIGH_QUIET_EN = ("quiet", "silent", "focus", "library", "noise-free")
_LOW_QUIET_ZH = ("嘈杂", "随便", "无所谓", "吵闹", "任何环境")
_LOW_QUIET_EN = ("noisy", "anywhere", "loud", "casual")


def _mock_parse(payload: Dict[str, Any], fingerprint: str) -> Dict[str, Any]:
    user_text = payload.get("user_text", "")
    now = payload.get("now", "")
    tasks = _extract_tasks(user_text, payload)
    if not tasks:
        tasks = [_fallback_task(user_text, now)]
    return {"tasks": tasks}


def _extract_tasks(user_text: str, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    segments = _split_task_text(user_text)
    return [_build_task(seg, payload) for seg in segments]


def _split_task_text(user_text: str) -> List[str]:
    """Split user input on common multi-task delimiters."""
    if not user_text.strip():
        return []
    # Try Chinese / English sentence breaks
    parts = re.split(r"[；;。\n]+", user_text)
    parts = [p.strip() for p in parts if p.strip()]
    if len(parts) <= 1:
        parts = re.split(r"(?:然后|还有|另外|接着|之后|其次|并且|此外|同时)", user_text)
        parts = [p.strip() for p in parts if p.strip()]
    if len(parts) <= 1:
        parts = re.split(r"(?:then|also|next|after|besides|additionally|and also)", user_text, flags=re.IGNORECASE)
        parts = [p.strip() for p in parts if p.strip()]
    return parts if parts else [user_text.strip()]


def _build_task(segment: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    title = _extract_title(segment)
    duration = _extract_duration(segment)
    is_deep = _classify_deep_work(segment, duration)
    deep_work_min = _estimate_deep_work_min(segment, duration)
    quietness = _extract_quietness(segment, is_deep)
    tags = _extract_tags(segment, is_deep)
    assumptions = _build_parser_assumptions(segment, duration, deep_work_min, quietness)
    now = payload.get("now", "")
    task_id = f"task_{abs(hash(segment)) % 100000:05d}"

    return {
        "task_id": task_id,
        "title": title,
        "description": segment.strip(),
        "duration_min": duration,
        "deadline": _infer_deadline(segment, now),
        "earliest_start": None,
        "series_id": None,
        "required_environment": ["desk"],
        "required_quietness": quietness,
        "dependencies": [],
        "must_be_contiguous": is_deep,
        "deep_work_min": deep_work_min,
        "tags": tags,
        "assumptions": assumptions,
    }


def _fallback_task(user_text: str, now: str = "") -> Dict[str, Any]:
    title = user_text.strip()[:40] if user_text.strip() else "未命名任务"
    return {
        "task_id": "task_fallback",
        "title": title,
        "description": user_text.strip(),
        "duration_min": 30,
        "deadline": _infer_deadline(user_text, now),
        "earliest_start": None,
        "series_id": None,
        "required_environment": ["desk"],
        "required_quietness": 0.35,
        "dependencies": [],
        "must_be_contiguous": False,
        "deep_work_min": 0,
        "tags": [],
        "assumptions": "无法从文本中推断细节，使用默认值",
    }


_EMOTION_TAGS_ZH = {
    "紧急": "紧急", "马上": "紧急", "立刻": "紧急", "赶紧": "紧急",
    "老板": "老板催办", "领导": "老板催办",
    "要死": "极度焦虑", "焦虑": "极度焦虑", "压力": "压力大",
    "摸鱼": "摸鱼", "随便": "低投入", "无所谓": "低投入",
    "专注": "需极度专注", "深度": "深度工作",
    "碎片": "碎片时间",
}
_EMOTION_TAGS_EN = {
    "urgent": "紧急", "asap": "紧急", "immediately": "紧急",
    "boss": "老板催办",
    "panic": "极度焦虑", "anxious": "极度焦虑", "stress": "压力大",
}


def _extract_tags(segment: str, is_deep: bool) -> List[str]:
    tags: List[str] = []
    lower = segment.lower()
    for kw, tag in _EMOTION_TAGS_ZH.items():
        if kw in segment and tag not in tags:
            tags.append(tag)
    for kw, tag in _EMOTION_TAGS_EN.items():
        if kw in lower and tag not in tags:
            tags.append(tag)
    if is_deep:
        tags.append("深度工作")
    return tags


def _infer_deadline(segment: str, now: str) -> str:
    """Infer an ISO deadline from urgency keywords relative to now."""
    if not now:
        base = datetime.now()
    else:
        try:
            base = datetime.fromisoformat(now)
        except (ValueError, TypeError):
            base = datetime.now()

    if any(w in segment for w in ("马上", "立刻", "立即", "10分钟", "5分钟", "赶紧")):
        return (base.replace(second=0, microsecond=0) + timedelta(minutes=30)).isoformat()
    if any(w in segment for w in ("今天", "马上要", "赶", "快点")):
        return base.replace(hour=23, minute=59, second=0, microsecond=0).isoformat()
    if any(w in segment for w in ("明天",)):
        return (base.replace(hour=23, minute=59, second=0, microsecond=0) + timedelta(days=1)).isoformat()
    return (base.replace(hour=23, minute=59, second=0, microsecond=0) + timedelta(days=3)).isoformat()



# ── Parser sub-heuristics ───────────────────────────────────────────────

def _extract_title(segment: str) -> str:
    cleaned = re.sub(r"\d+\s*(?:小时|分钟|min|hour|hr?|minute)s?\b", "", segment, flags=re.IGNORECASE)
    cleaned = re.sub(r"(?:大概|大约|需要|估计|可能|应该|我想|帮我)", "", cleaned)
    cleaned = cleaned.strip().lstrip("，,、").strip()
    if len(cleaned) > 50:
        cleaned = cleaned[:47] + "..."
    return cleaned if cleaned else "未命名任务"


def _extract_duration(segment: str) -> int:
    # Hours
    m = re.search(r"(\d+(?:\.\d+)?)\s*小时", segment)
    if m:
        return max(5, int(float(m.group(1)) * 60))
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:hour|hr)\b", segment, re.IGNORECASE)
    if m:
        return max(5, int(float(m.group(1)) * 60))
    m = re.search(r"半天", segment)
    if m:
        return 240

    # Minutes
    m = re.search(r"(\d+)\s*分钟", segment)
    if m:
        return max(5, int(m.group(1)))
    m = re.search(r"(\d+)\s*(?:min|minute)\b", segment, re.IGNORECASE)
    if m:
        return max(5, int(m.group(1)))

    # Contextual defaults
    if _any_match(segment, _DEEP_WORK_ZH + _DEEP_WORK_EN):
        return 90
    if _any_match(segment, ("阅读", "复习", "read", "review", "学习", "study")):
        return 60
    if _any_match(segment, _SHALLOW_ZH + _SHALLOW_EN):
        return 20

    return 30


def _classify_deep_work(segment: str, estimated_minutes: int) -> bool:
    return _estimate_deep_work_min(segment, estimated_minutes) > 0


def _estimate_deep_work_min(segment: str, duration: int) -> int:
    lower = segment.lower()
    if _any_match(segment, _SHALLOW_ZH + _SHALLOW_EN) or _any_match(
        segment, ("跑步", "运动", "健身", "游泳", "锻炼", "骑车", "体测")
    ):
        return 0
    if "kv cache" in lower or "kv缓存" in segment or "kv 缓存" in segment:
        return duration
    if "作业" in segment and _any_match(segment, ("高数", "数学", "微积分", "线代", "calculus")):
        return min(duration, max(15, duration // 4))
    if _any_match(segment, ("实验报告", "数电", "模电")) and _any_match(
        segment, ("报告", "写", "撰写")
    ):
        return min(duration, max(30, duration // 2))
    if _any_match(segment, _DEEP_WORK_ZH + _DEEP_WORK_EN):
        if duration >= 90:
            return min(duration, max(45, int(duration * 0.75)))
        return min(duration, max(20, int(duration * 0.55)))
    return 0


def _extract_quietness(segment: str, is_deep_work: bool) -> float:
    if _any_match(segment, _HIGH_QUIET_ZH + _HIGH_QUIET_EN):
        return 0.85
    if _any_match(segment, _LOW_QUIET_ZH + _LOW_QUIET_EN):
        return 0.15
    if is_deep_work:
        return 0.70
    return 0.35


def _build_parser_assumptions(segment: str, mins: int, deep_work_min: int, quiet: float) -> str:
    parts: List[str] = []
    if deep_work_min > 0:
        parts.append(f"推断深度专注约{deep_work_min}分钟（总时长{mins}分钟）")
    elif mins > 0:
        parts.append("推断无深度专注时段")
    if quiet >= 0.7:
        parts.append("推断需要安静环境")
    elif quiet <= 0.2:
        parts.append("推断对环境无特殊要求")
    duration_matched = bool(
        re.search(r"(?:小时|分钟|hour|min|半天)", segment, re.IGNORECASE)
    )
    if duration_matched:
        parts.append(f"从文本提取时长约{mins}分钟")
    else:
        parts.append(f"未检测到时长关键词，默认{mins}分钟")
    return "；".join(parts) if parts else "基于默认假设"


# ═══════════════════════════════════════════════════════════════════════════
#  Scorer
# ═══════════════════════════════════════════════════════════════════════════

# ── Chinese + English keyword tables ────────────────────────────────────

_HIGH_URGENCY = (
    "紧急", "马上", "立刻", "立即", "尽快", "迫在眉睫", "火速",
    "urgent", "asap", "immediately", "critical deadline",
)
_MED_URGENCY = ("今天", "快点", "赶", "deadline", "today", "soon", "due")

_HIGH_IMPORTANCE = (
    "重要", "关键", "核心", "必须", "至关重要", "必不可少",
    "critical", "important", "essential", "vital", "crucial", "key",
    "priority", "high-stakes",
)
_MED_IMPORTANCE = ("需要", "应该", "最好", "should", "needed", "recommended")

_HIGH_COMPLEXITY = (
    "复杂", "难", "困难", "高数", "算法", "数学", "棘手",
    "complex", "difficult", "hard", "algorithm", "math", "calculus",
    "challenging", "advanced",
)
_MED_COMPLEXITY = ("中等", "一般", "medium", "moderate", "review", "draft", "常规")

_HIGH_COGNITIVE = (
    "深度工作", "专注", "烧脑", "费脑", "高度集中",
    "deep work", "focus", "cognitive", "concentrate", "intense",
    "heavy thinking", "brain-intensive",
)
_MED_COGNITIVE = ("阅读", "学习", "规划", "整理", "read", "study", "plan", "organize", "prepare")

_HIGH_BLOCK = (
    "不间断", "连续", "整块", "打断", "连贯",
    "contiguous", "uninterrupted", "block", "no interruption",
    "continuous", "flow",
)

_HIGH_ENV = (
    "实验室", "设备", "办公室", "特定地点", "必须在",
    "lab", "equipment", "office", "specific", "on-site",
    "必须用", "专用",
)


def _mock_score(payload: Dict[str, Any], fingerprint: str) -> Dict[str, Any]:
    task = payload.get("task", {})
    task_id = str(task.get("task_id", "unknown"))
    profile = payload.get("profile", {})
    now = payload.get("now", "")
    deadline = task.get("deadline", "")
    duration = int(task.get("duration_min", 30))

    task_text = _build_task_text(task)
    hours_left = _safe_hours(now, deadline)
    jitter = (int(fingerprint[:2], 16) % 7 - 3) / 100

    urgency = _score_urgency(hours_left, task_text, jitter)
    importance = _score_importance(task_text, task, jitter)
    complexity = _score_complexity(task_text, duration, jitter)
    cognitive_load = _score_cognitive_load(task_text, duration, jitter)
    block_integrity = _score_block_integrity(task, task_text, duration, profile, jitter)
    env_dep = _score_env_dep(task, task_text, jitter)
    quietness = _score_quietness(task, cognitive_load, jitter)

    # Dampen trivial tasks
    if _any_match(task_text, ("email", "邮件", "reply", "回复")):
        complexity *= 0.45
        cognitive_load *= 0.50
    if _any_match(task_text, ("message", "消息", "chat", "聊天")):
        complexity *= 0.55
        cognitive_load *= 0.55

    scores = {
        "urgency": clamp(urgency),
        "importance": clamp(importance),
        "complexity": clamp(complexity),
        "cognitive_load": clamp(cognitive_load),
        "block_integrity": clamp(block_integrity),
        "environment_dependency": clamp(env_dep),
        "quietness_need": clamp(quietness),
    }

    confidence = clamp(0.85 - abs(jitter) * 1.8)
    rationale = _build_score_rationale(scores, task_text, hours_left)

    # Per-vote format compatible with ScoringAgent._aggregate
    return {
        "task_id": task_id,
        "scores": {
            "urgency": scores["urgency"],
            "complexity": scores["complexity"],
            "cognitive_load": scores["cognitive_load"],
            "block_integrity": scores["block_integrity"],
            "environment_dependency": scores["environment_dependency"],
            "quietness_need": scores["quietness_need"],
        },
        "confidence": confidence,
        "rationale": rationale,
    }


# ── Smooth scoring functions ────────────────────────────────────────────

def _score_urgency(hours_left: float, text: str, jitter: float) -> float:
    """Smooth urgency curve instead of hard tiers."""
    if hours_left <= 1:
        base = 0.96
    elif hours_left <= 4:
        base = 0.85 + 0.11 * (1 - (hours_left - 1) / 3)
    elif hours_left <= 12:
        base = 0.68 + 0.17 * (1 - (hours_left - 4) / 8)
    elif hours_left <= 24:
        base = 0.52 + 0.16 * (1 - (hours_left - 12) / 12)
    elif hours_left <= 72:
        base = 0.38 + 0.14 * (1 - (hours_left - 24) / 48)
    elif hours_left <= 168:
        base = 0.25 + 0.13 * (1 - (hours_left - 72) / 96)
    else:
        base = 0.15 + 0.10 * max(0, 1 - (hours_left - 168) / 504)

    if _any_match(text, _HIGH_URGENCY):
        base = max(base, 0.90)
    elif _any_match(text, _MED_URGENCY):
        base = max(base, base + 0.12)

    return base + jitter * 0.4


def _score_importance(text: str, task: Dict[str, Any], jitter: float) -> float:
    base = 0.45

    if _any_match(text, _HIGH_IMPORTANCE):
        base = max(base, 0.84)
    elif _any_match(text, _MED_IMPORTANCE):
        base = max(base, 0.60)

    tags = [str(t).lower() for t in task.get("tags", [])]
    if any(t in ("critical", "important", "关键", "重要", "priority") for t in tags):
        base = max(base, 0.80)

    deps = task.get("dependencies", [])
    if deps:
        base = min(1.0, base + 0.07 * min(len(deps), 5))

    return base + jitter * 0.3


def _score_complexity(text: str, duration: int, jitter: float) -> float:
    if _any_match(text, _HIGH_COMPLEXITY):
        base = 0.80
    elif _any_match(text, _MED_COMPLEXITY):
        base = 0.55
    else:
        base = 0.32

    base += min(0.14, duration / 650)
    return base + jitter * 0.35


def _score_cognitive_load(text: str, duration: int, jitter: float) -> float:
    if _any_match(text, _HIGH_COGNITIVE):
        base = 0.84
    elif _any_match(text, _MED_COGNITIVE):
        base = 0.55
    else:
        base = 0.32

    base += min(0.12, duration / 750)
    return base + jitter * 0.35


def _score_block_integrity(
    task: Dict[str, Any], text: str, duration: int, profile: Dict[str, Any], jitter: float
) -> float:
    base = min(1.0, 0.28 + duration / 170)

    if _any_match(text, _HIGH_BLOCK):
        base = min(1.0, base + 0.18)

    deep_hints = ("review", "paper", "deep", "gaoshu", "报告", "论文", "分析", "设计",
                  "research", "architecture", "code", "编程")
    if _any_match(text, deep_hints):
        base = min(1.0, base + 0.16)

    max_deep = profile.get("max_daily_deep_work_min", 180)
    if max_deep < 150 and base > 0.55:
        base = min(1.0, base + 0.10)

    return base + jitter * 0.25


def _score_env_dep(task: Dict[str, Any], text: str, jitter: float) -> float:
    required_env = task.get("required_environment", [])
    base = min(1.0, 0.25 + 0.22 * len(required_env))

    if _any_match(text, _HIGH_ENV):
        base = min(1.0, base + 0.22)

    return base + jitter * 0.25


def _score_quietness(task: Dict[str, Any], cognitive_load: float, jitter: float) -> float:
    explicit = float(task.get("required_quietness", 0.0))
    return max(explicit, cognitive_load * 0.72) + jitter * 0.2


def _build_score_rationale(scores: Dict[str, float], text: str, hours_left: float) -> str:
    parts: List[str] = []
    if scores["urgency"] > 0.70:
        parts.append(f"紧迫({hours_left:.0f}h)")
    if scores["importance"] > 0.70:
        parts.append("高重要度")
    if scores["complexity"] > 0.70:
        parts.append("高复杂度")
    if scores["cognitive_load"] > 0.70:
        parts.append("高认知负荷")
    if scores["block_integrity"] > 0.70:
        parts.append("需整块时间")
    if scores["environment_dependency"] > 0.60:
        parts.append("依赖特定环境")
    if not parts:
        parts.append("各项适中")
    return "mock评分: " + "; ".join(parts)


# ── Shared helpers ──────────────────────────────────────────────────────

def _build_task_text(task: Dict[str, Any]) -> str:
    return " ".join(
        [
            str(task.get("title", "")),
            str(task.get("description", "")),
            " ".join(str(t) for t in task.get("tags", [])),
        ]
    ).lower()


def _safe_hours(now: str, deadline: str) -> float:
    if not now or not deadline:
        return 72.0
    try:
        delta = datetime.fromisoformat(deadline) - datetime.fromisoformat(now)
        return max(0.0, delta.total_seconds() / 3600)
    except (ValueError, TypeError, OverflowError):
        return 72.0


def _any_match(text: str, keywords: tuple) -> bool:
    return any(kw in text for kw in keywords)


def clamp(value: float) -> float:
    return max(0.0, min(1.0, value))
