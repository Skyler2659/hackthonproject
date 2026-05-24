from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from llm_client import DeepSeekLLMClient, LLMClient
from models import ScheduleBlock, ScheduleResult, Task, TaskScore, UserProfile


SYSTEM_PROMPT = """
You are a schedule refinement reviewer after a deterministic solver has produced a draft plan.

The user's lifestyle questionnaire is SOFT guidance only (passed as profile_soft_hints). Do NOT treat it as absolute law.
Hard rules you must respect when proposing changes:
- No overlapping blocks
- Respect task dependencies (parent ends before child starts)
- Each block must end on or before the task deadline
- Honor fixed manual_start/manual_end if present
- Keep semantic transition buffers (e.g. exercise before study may need a gap)

Your job: review density, pacing, conflicts, and unscheduled tasks; suggest minimal JSON adjustments.

─── OUTPUT FORMAT ───
Output ONLY one JSON object starting with "{" ending with "}".

{
  "density": "too_dense|balanced|too_sparse",
  "block_adjustments": [
    {"task_id": "id", "new_start": "YYYY-MM-DDTHH:MM:SS", "reason": "≤30字"}
  ],
  "retry_unscheduled": ["task_id"],
  "leave_unscheduled": [
    {"task_id": "id", "reason": "≤40字中文，告诉用户为何需手动安排"}
  ],
  "summary": "≤80字中文，给用户看的整体说明"
}

Rules:
- block_adjustments: only shift existing scheduled tasks; use ISO local times; keep same duration.
- retry_unscheduled: task_ids still not in schedule that could fit with moderate intensity (slightly outside preferred windows OK).
- leave_unscheduled: tasks that truly cannot fit before DDL even with relaxation.
- Prefer balanced spacing: flag too_dense if many gaps <15min or back-to-back high cognitive_load; flag too_sparse if large idle gaps between urgent tasks.
- Do not schedule tasks before `now` unless already placed there.
- If nothing to change, return empty arrays and explain in summary.
""".strip()


class ScheduleRefinementAgent:
    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self._llm = llm_client or DeepSeekLLMClient.from_env()

    def review(
        self,
        result: ScheduleResult,
        tasks: List[Task],
        scores: Dict[str, TaskScore],
        profile: UserProfile,
        profile_soft_hints: str,
        now: datetime,
    ) -> Dict[str, Any]:
        task_by_id = {task.task_id: task for task in tasks}
        payload = {
            "mode": "schedule_refinement",
            "now": now.isoformat(),
            "profile_soft_hints": profile_soft_hints,
            "scheduled_blocks": [
                {
                    "task_id": block.task_id,
                    "title": block.title,
                    "start": block.start.isoformat(),
                    "end": block.end.isoformat(),
                    "priority": block.priority,
                    "reason": block.reason,
                }
                for block in sorted(result.blocks, key=lambda item: item.start)
            ],
            "unscheduled_task_ids": list(result.unscheduled_task_ids),
            "tasks": [
                {
                    "task_id": task.task_id,
                    "title": task.title,
                    "duration_min": task.duration_min,
                    "deep_work_min": task.deep_work_min,
                    "deadline": task.deadline.isoformat(),
                    "dependencies": list(task.dependencies),
                    "required_quietness": task.required_quietness,
                    "manual_start": task.manual_start.isoformat() if task.manual_start else None,
                    "manual_end": task.manual_end.isoformat() if task.manual_end else None,
                    "scores": _score_payload(scores.get(task.task_id)),
                }
                for task in tasks
                if task.task_id in task_by_id
            ],
        }
        return self._llm.generate_json(system_prompt=SYSTEM_PROMPT, payload=payload)


def _score_payload(score: TaskScore | None) -> Dict[str, float]:
    if score is None:
        return {}
    normalized = score.normalized()
    return {
        "urgency": normalized.urgency,
        "cognitive_load": normalized.cognitive_load,
        "block_integrity": normalized.block_integrity,
        "quietness_need": normalized.quietness_need,
    }
