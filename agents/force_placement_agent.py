from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from llm_client import DeepSeekLLMClient, LLMClient
from models import Task, TaskScore, UserProfile


SYSTEM_PROMPT = """
You are a force-placement agent. The user clicked "auto join" for a task that failed normal scheduling.
Your job is to pick ONE candidate time slot from the list provided.

─── HARD RULES (already satisfied by every candidate) ───
- No overlap with existing blocks
- Ends on or before task deadline
- Respects dependencies and fixed manual windows
- Respects minimum transition gaps vs neighbors (shown as gap_before_min / gap_after_min)

─── DO NOT optimize for ───
- Deep work daily budget
- Quietness / environment / focus preferences
- User questionnaire time windows (soft hints only)

─── DO optimize for ───
- Reasonable spacing: avoid cramming if a slot has gap_before+gap_after < 15 unless urgent
- Urgent tasks (high urgency) may use tighter gaps and slots closer to deadline
- Prefer slots that leave breathing room after intense neighbors (see neighbor titles)
- Avoid placing cognitively heavy tasks immediately after physical exercise without enough gap (candidates already enforce min gap; prefer more margin when possible)
- If multiple slots are fine, prefer not the very first minute of the day unless urgency is high

─── OUTPUT ───
ONLY valid JSON:
{
  "task_id": "string",
  "chosen_slot_id": "string",
  "reason": "≤40字中文，说明为何选这个时段"
}
chosen_slot_id MUST be one of the candidate slot_id values exactly.
""".strip()


class ForcePlacementAgent:
    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self._llm = llm_client or DeepSeekLLMClient.from_env()

    def choose_slot(
        self,
        task: Task,
        score: TaskScore,
        candidates: List[Dict[str, Any]],
        existing_blocks: List[Dict[str, Any]],
        profile_soft_hints: str,
        now: datetime,
    ) -> Dict[str, Any]:
        payload = {
            "mode": "force_placement",
            "now": now.isoformat(),
            "profile_soft_hints": profile_soft_hints,
            "task": {
                "task_id": task.task_id,
                "title": task.title,
                "description": task.description,
                "duration_min": task.duration_min,
                "deadline": task.deadline.isoformat(),
                "dependencies": list(task.dependencies),
                "tags": list(task.tags),
            },
            "scores": {
                "urgency": score.urgency,
                "cognitive_load": score.cognitive_load,
                "block_integrity": score.block_integrity,
            },
            "existing_blocks": existing_blocks,
            "candidates": candidates,
        }
        return self._llm.generate_json(system_prompt=SYSTEM_PROMPT, payload=payload)
