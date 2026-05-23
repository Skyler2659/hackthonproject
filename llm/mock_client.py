from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from llm.base import ReplayGuard


class MockLLMClient(ReplayGuard):
    """Deterministic local fallback for tests and offline demos."""

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
            self._response_cache[fingerprint] = mock_score(payload, fingerprint)
        return dict(self._response_cache[fingerprint])


def mock_score(payload: Dict[str, Any], fingerprint: str) -> Dict[str, Any]:
    task = payload["task"]
    profile = payload["profile"]
    task_text = build_task_text(task)
    hours_left = hours_until_deadline(payload["now"], task["deadline"])
    complexity = keyword_score(task_text, HIGH_COMPLEXITY, MEDIUM_COMPLEXITY)
    cognitive_load = keyword_score(task_text, HIGH_COGNITIVE_LOAD, MEDIUM_COGNITIVE_LOAD)

    if "email" in task_text:
        complexity *= 0.45
        cognitive_load *= 0.5

    jitter = (int(fingerprint[:2], 16) % 7 - 3) / 100
    scores = {
        "urgency": clamp(urgency_from_deadline(hours_left) + jitter),
        "complexity": clamp(complexity + jitter),
        "cognitive_load": clamp(cognitive_load + jitter),
        "block_integrity": clamp(block_integrity(task, profile, task_text) + jitter),
        "quietness_need": clamp(quietness_need(task, cognitive_load) + jitter),
        "environment_dependency": clamp(environment_dependency(task) + jitter),
    }

    return {
        "task_id": task["task_id"],
        "scores": scores,
        "confidence": clamp(0.84 - abs(jitter)),
        "rationale": "mock semantic score from deadline, keywords, duration, and profile",
    }


HIGH_COMPLEXITY = ("math", "calculus", "algorithm", "gaoshu", "paper", "research")
MEDIUM_COMPLEXITY = ("review", "homework", "draft", "reading")
HIGH_COGNITIVE_LOAD = ("math", "calculus", "algorithm", "gaoshu", "paper", "architecture")
MEDIUM_COGNITIVE_LOAD = ("read", "review", "plan", "organize")


def build_task_text(task: Dict[str, Any]) -> str:
    return " ".join(
        [
            task.get("title", ""),
            task.get("description", ""),
            " ".join(task.get("tags", [])),
        ]
    ).lower()


def hours_until_deadline(now: str, deadline: str) -> float:
    delta = datetime.fromisoformat(deadline) - datetime.fromisoformat(now)
    return max(0.0, delta.total_seconds() / 3600)


def urgency_from_deadline(hours_left: float) -> float:
    if hours_left <= 6:
        return 0.95
    if hours_left <= 24:
        return 0.82
    if hours_left <= 72:
        return 0.62
    return 0.35


def keyword_score(text: str, high: tuple[str, ...], medium: tuple[str, ...]) -> float:
    if any(word in text for word in high):
        return 0.88
    if any(word in text for word in medium):
        return 0.62
    return 0.35


def block_integrity(task: Dict[str, Any], profile: Dict[str, Any], text: str) -> float:
    duration = int(task.get("duration_min", 30))
    score = min(1.0, 0.25 + duration / 180)
    if any(word in text for word in ("review", "paper", "deep", "gaoshu")):
        score = min(1.0, score + 0.25)
    if profile.get("max_daily_deep_work_min", 180) < 150 and score > 0.6:
        score = min(1.0, score + 0.12)
    return score


def quietness_need(task: Dict[str, Any], cognitive_load: float) -> float:
    return max(float(task.get("required_quietness", 0.0)), cognitive_load * 0.8)


def environment_dependency(task: Dict[str, Any]) -> float:
    required_environment = task.get("required_environment", [])
    return min(1.0, 0.25 + 0.25 * len(required_environment))


def clamp(value: float) -> float:
    return max(0.0, min(1.0, value))
