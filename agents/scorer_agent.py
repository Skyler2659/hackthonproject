from __future__ import annotations

from datetime import datetime
from statistics import mean, pstdev
from typing import Dict, List

from llm_client import DeepSeekLLMClient, LLMClient
from models import Task, TaskScore, UserProfile, clamp01


SYSTEM_PROMPT = """
You are a cognitive-aware task scoring agent.
Return strict JSON only. No markdown.

Schema:
{
  "task_id": "string",
  "scores": {
    "urgency": 0.0,
    "complexity": 0.0,
    "cognitive_load": 0.0,
    "block_integrity": 0.0,
    "environment_dependency": 0.0,
    "quietness_need": 0.0
  },
  "confidence": 0.0,
  "rationale": "short reason"
}

Score every numeric field in [0, 1].
Scoring dimensions:
1. urgency: deadline pressure and consequence of delay.
2. complexity: reasoning difficulty and uncertainty.
3. cognitive_load: required mental energy.
4. block_integrity: need for uninterrupted time.
5. environment_dependency: dependence on location, device, context, or resources.

Personalization rules:
- Use chronotype and energy_curve to infer cognitive fit.
- If max_daily_deep_work_min is low, increase block_integrity sensitivity.
- If the deadline is near, urgency must dominate complexity.
- If required_environment is strict, raise environment_dependency.
- Do not invent missing facts; lower confidence instead.
""".strip()


class ScoringAgent:
    def __init__(self, llm_client: LLMClient | None = None, ensemble_size: int = 3) -> None:
        self._llm = llm_client or DeepSeekLLMClient.from_env()
        self._ensemble_size = max(1, ensemble_size)

    def score_task(self, task: Task, profile: UserProfile, now: datetime) -> TaskScore:
        votes = [
            self._single_vote(task=task, profile=profile, now=now, sample_index=index)
            for index in range(self._ensemble_size)
        ]
        return self._aggregate(task.task_id, votes)

    def score_tasks(
        self,
        tasks: List[Task],
        profile: UserProfile,
        now: datetime,
    ) -> Dict[str, TaskScore]:
        return {task.task_id: self.score_task(task, profile, now) for task in tasks}

    def _single_vote(
        self,
        task: Task,
        profile: UserProfile,
        now: datetime,
        sample_index: int,
    ) -> Dict[str, object]:
        payload = {
            "now": now.isoformat(),
            "sample_index": sample_index,
            "task": {
                "task_id": task.task_id,
                "title": task.title,
                "description": task.description,
                "duration_min": task.duration_min,
                "deadline": task.deadline.isoformat(),
                "earliest_start": task.earliest_start.isoformat() if task.earliest_start else None,
                "series_id": task.series_id,
                "required_quietness": task.required_quietness,
                "required_environment": list(task.required_environment),
                "dependencies": list(task.dependencies),
                "tags": list(task.tags),
            },
            "profile": {
                "user_id": profile.user_id,
                "chronotype": profile.chronotype,
                "energy_curve": profile.energy_curve,
                "available_windows": [
                    [start.strftime("%H:%M"), end.strftime("%H:%M")]
                    for start, end in profile.available_windows
                ],
                "max_daily_deep_work_min": profile.max_daily_deep_work_min,
                "preferred_environments": list(profile.preferred_environments),
            },
        }
        return self._llm.generate_json(
            system_prompt=SYSTEM_PROMPT,
            payload=payload,
            idempotency_key=f"{profile.user_id}:{task.task_id}:score:{sample_index}",
        )

    @staticmethod
    def _aggregate(task_id: str, votes: List[Dict[str, object]]) -> TaskScore:
        dimensions = [
            "urgency",
            "complexity",
            "cognitive_load",
            "block_integrity",
            "environment_dependency",
            "quietness_need",
        ]
        values = {
            name: [ScoringAgent._score_value(vote, name) for vote in votes]
            for name in dimensions
        }
        confidence_values = [float(vote["confidence"]) for vote in votes]
        dispersion = mean(pstdev(values[name]) for name in dimensions)

        return TaskScore(
            task_id=task_id,
            urgency=mean(values["urgency"]),
            complexity=mean(values["complexity"]),
            cognitive_load=mean(values["cognitive_load"]),
            block_integrity=mean(values["block_integrity"]),
            environment_dependency=mean(values["environment_dependency"]),
            quietness_need=mean(values["quietness_need"]),
            confidence=clamp01(mean(confidence_values) - dispersion),
            rationale="ensemble average; confidence penalized by vote dispersion",
            agent_votes=votes,
        ).normalized()

    @staticmethod
    def _score_value(vote: Dict[str, object], name: str) -> float:
        scores = vote.get("scores", {})
        if not isinstance(scores, dict):
            return 0.0
        return float(scores.get(name, 0.0))
