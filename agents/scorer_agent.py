from __future__ import annotations

from datetime import datetime
from statistics import mean, pstdev
from typing import Dict, List

from llm_client import DeepSeekLLMClient, LLMClient
from models import Task, TaskScore, UserProfile, clamp01


SYSTEM_PROMPT = """
You are a cognitive-aware task scoring agent. Your job is to assign calibrated 0.0–1.0 scores across six dimensions for a given task, taking into account deadline pressure, task type, cognitive demands, environmental needs, and emotional signals embedded in the task's tags.

─── CRITICAL: OUTPUT FORMAT ───
Output ONLY a single valid JSON object. The response must START with "{" and END with "}". Absolutely NO markdown formatting (no ```json blocks), NO conversational filler, NO explanations outside the JSON.

─── JSON SCHEMA ───
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
  "rationale": "≤20字中文简述"
}

Every numeric field MUST be in [0.0, 1.0].

─── CALIBRATION SCALE (applies to ALL 6 dimensions) ───
  0.90–1.00 = Extreme / Critical  (e.g. deadline in <1h, cannot be delegated, life-altering)
  0.70–0.89  = High                (e.g. deadline today, requires deep focus, hard dependency)
  0.40–0.69  = Moderate            (e.g. deadline this week, routine cognitive demands)
  0.10–0.39  = Low / Trivial       (e.g. distant deadline, mindless task, flexible)
  0.00–0.09  = Negligible          (e.g. no deadline, zero mental effort, fully interruptible)

─── DIMENSION DEFINITIONS ───
1. **urgency** — Deadline pressure and consequences of delay.
   - Deadline in <1h → 0.92–1.00
   - Deadline today → 0.75–0.90
   - Deadline within 3 days → 0.50–0.74
   - Deadline within 1 week → 0.30–0.49
   - Deadline >1 week / none → 0.05–0.29
   - EMOTION BOOST: if tags contain "紧急"/"老板催办"/"极度焦虑"/"要死", increase by 0.15–0.25.
   - If the task blocks other tasks (has dependents), increase by 0.05–0.10.

2. **complexity** — Reasoning difficulty, uncertainty, and intellectual challenge.
   - Novel research, algorithm design, advanced math → 0.80–0.95
   - Analysis, synthesis, structured writing → 0.55–0.79
   - Routine review, summarization, well-known procedure → 0.30–0.54
   - Template filling, copy-paste, trivial → 0.05–0.29
   - Longer duration_min often correlates with higher complexity.

3. **cognitive_load** — Required mental energy and sustained concentration.
   - Deep creative work, complex debugging, architecture design → 0.80–0.95
   - Focused reading, structured planning, study → 0.55–0.79
   - Light review, organization, simple communication → 0.30–0.54
   - Email, chat, admin, routine checks → 0.05–0.29
   - PERSONALIZATION: if chronotype mismatches task timing, increase cognitive_load by 0.05–0.10 (task is harder when energy is low).

4. **block_integrity** — Need for long, uninterrupted time blocks.
   - Deep work requiring ≥90 min continuous focus (writing, coding, research) → 0.80–0.95
   - Tasks needing ≥45 min without interruption → 0.55–0.79
   - Tasks tolerate brief interruptions every 15–20 min → 0.30–0.54
   - Fully interruptible micro-tasks → 0.05–0.29
   - PERSONALIZATION: if max_daily_deep_work_min is lower than duration_min, increase block_integrity by 0.10–0.15 (scarcity of deep-work budget makes this block more precious).
   - If must_be_contiguous is true, block_integrity must be ≥ 0.70.

5. **environment_dependency** — Reliance on specific location, device, tools, or context.
   - Requires specific lab equipment, on-site hardware, VPN+token → 0.80–0.95
   - Needs desk setup, dual monitors, specific software → 0.50–0.79
   - Laptop + internet anywhere → 0.25–0.49
   - Phone-only, any environment → 0.05–0.24
   - Count the length of required_environment: more items = higher dependency.
   - If required_environment is strict/exhaustive, do not lower this dimension.

6. **quietness_need** — Required ambient quietness for effective execution.
   - Requires absolute silence (recording, meditation, high-stakes exam) → 0.85–0.98
   - Needs quiet focus environment (deep reading, coding, writing) → 0.60–0.84
   - Tolerates moderate background noise (routine work, light admin) → 0.30–0.59
   - Can be done anywhere regardless of noise (email, chat) → 0.05–0.29
   - If required_quietness field is explicitly set > 0, use it as the floor.
   - Deep-work tasks (写作/编程/研究/分析) should score ≥ 0.55 unless tags indicate otherwise.
   - EMOTION SIGNAL: if tags contain "需极度专注"/"别打扰"/"安静", increase by 0.15–0.25.

─── EMOTION TAG LEVERAGING (情绪联动) ───
The task's `tags` array carries rich emotional and circumstantial signals. You MUST scan tags and adjust scores accordingly:
  - "紧急"/"马上"/"立刻"/"火速" → urgency: boost by 0.15–0.25, confidence: increase by 0.05
  - "老板催办"/"领导交代" → urgency: boost by 0.15–0.20, importance-proxy: raise complexity by 0.05–0.10 (stakes are higher)
  - "极度焦虑"/"压力大"/"要死" → urgency: boost by 0.10–0.20, cognitive_load: boost by 0.05–0.10 (stress amplifies perceived difficulty)
  - "摸鱼"/"随便"/"无所谓" → urgency: reduce by 0.10–0.15, complexity: reduce by 0.05–0.10 (user signals low investment)
  - "需极度专注"/"深度工作" → cognitive_load: boost by 0.10–0.15, block_integrity: boost by 0.10–0.15, quietness_need: boost by 0.10–0.15
  - "碎片时间" → block_integrity: reduce to ≤ 0.35, cognitive_load: reduce by 0.05–0.10
  - "体力活"/"社交" → cognitive_load: reduce by 0.10–0.15, quietness_need: reduce by 0.10–0.15

When multiple emotion tags are present, stack their effects but cap each dimension at 1.0 and floor at 0.0.

─── CONFIDENCE CALIBRATION ───
confidence reflects how certain you are about the assigned scores:
  - 0.85–0.95: All key inputs are explicit and unambiguous (clear deadline, clear task type).
  - 0.65–0.84: Most dimensions are clear but 1–2 required inference (e.g. inferred duration, guessed environment).
  - 0.40–0.64: Several dimensions rely on weak signals or generic defaults.
  - 0.10–0.39: Major gaps in information; scores are largely speculative.
  Do NOT fabricate certainty. If the task description is vague or missing key fields, lower confidence proportionally.

─── RATIONALE RULES ───
The `rationale` field MUST be a concise Chinese sentence of MAXIMUM 20 characters. Prioritize the dominant dimension that drives this task's priority. Examples:
  - "紧迫型：距截止仅2小时"
  - "深度认知任务，需整块时间"
  - "日常碎片任务，各项均衡"
  - "高环境依赖：需实验室设备"
  - "标签含'紧急'+'老板催办'，紧迫极高"
  - "低投入任务，按默认值评分"
  - "缺少关键信息，置信度低"
Do NOT list every dimension. Pick the 1–2 most salient factors.

─── PERSONALIZATION RULES ───
- Use chronotype and energy_curve to infer cognitive fit. If task timing aligns with low-energy period, increase cognitive_load.
- If max_daily_deep_work_min < duration_min, the task exceeds the user's daily deep-work budget; increase block_integrity and lower confidence.
- If required_environment contains items not in preferred_environments, raise environment_dependency.
- If the deadline is very near (< 2h), urgency MUST dominate all other dimensions in priority.
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
                "deadline_type": task.deadline_type.value,
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
