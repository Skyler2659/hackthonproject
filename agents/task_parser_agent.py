from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterable

from llm_client import DeepSeekLLMClient, LLMClient
from models import Task, UserProfile


SYSTEM_PROMPT = """
You are a task parser and normalizer for a cognitive-aware scheduler.
Return strict JSON only. No markdown.

The user gives one natural-language task request. Infer the scheduler fields
that a normal user should not have to fill manually.

Schema:
{
  "title": "concise task title",
  "description": "normalized task description and useful context",
  "duration_min": 60,
  "deadline": "YYYY-MM-DDTHH:MM:SS",
  "earliest_start": null,
  "series_id": null,
  "required_environment": ["desk"],
  "required_quietness": 0.45,
  "dependencies": [],
  "tags": ["writing"],
  "confidence": 0.0,
  "assumptions": "short note about inferred duration/deadline"
}

Rules:
- Parse exactly one task.
- duration_min must be an integer from 5 to 480, preferably a multiple of 5.
- If fixed_deadline is provided, deadline must exactly equal fixed_deadline.
- If fixed_deadline is null, infer deadline from the user's wording, current time,
  and urgency. If ambiguous, choose a reasonable planning deadline in the next
  three days, never in the past.
- required_environment must only use allowed_environment_options.
- dependencies may only contain task_id values from existing_tasks, and only when
  the user clearly references an existing task as a prerequisite.
- Use the user profile to infer quietness and environment needs.
- Do not invent facts; when uncertain, make conservative assumptions and lower
  confidence.
""".strip()


class TaskParserAgent:
    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self._llm = llm_client or DeepSeekLLMClient.from_env()

    def parse_task(
        self,
        user_text: str,
        profile: UserProfile,
        now: datetime,
        allowed_environment_options: Iterable[str],
        fixed_deadline: datetime | None = None,
        existing_tasks: Iterable[Task] = (),
    ) -> Dict[str, Any]:
        payload = {
            "now": now.isoformat(),
            "user_text": user_text,
            "fixed_deadline": fixed_deadline.isoformat() if fixed_deadline else None,
            "allowed_environment_options": list(allowed_environment_options),
            "existing_tasks": [
                {
                    "task_id": task.task_id,
                    "title": task.title,
                    "series_id": task.series_id,
                    "deadline": task.deadline.isoformat(),
                    "status": task.status.value,
                }
                for task in existing_tasks
            ],
            "profile": {
                "user_id": profile.user_id,
                "chronotype": profile.chronotype,
                "energy_curve": profile.energy_curve,
                "available_windows": [
                    [start.strftime("%H:%M"), end.strftime("%H:%M")]
                    for start, end in profile.available_windows
                ],
                "quiet_windows": [
                    [start.strftime("%H:%M"), end.strftime("%H:%M")]
                    for start, end in profile.quiet_windows
                ],
                "max_daily_deep_work_min": profile.max_daily_deep_work_min,
                "preferred_environments": list(profile.preferred_environments),
            },
        }
        return self._llm.generate_json(
            system_prompt=SYSTEM_PROMPT,
            payload=payload,
        )
