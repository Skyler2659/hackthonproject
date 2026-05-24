from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, Iterable, List

from llm_client import DeepSeekLLMClient, LLMClient
from models import Task, UserProfile


SYSTEM_PROMPT = """
You are a task-intake clarification agent for a cognitive-aware scheduler.
The user often gives brief, colloquial Chinese requests. Your job is to decide whether
the input has ENOUGH concrete information to schedule reliably, or whether the UI
should ask 1–4 short follow-up questions first.

─── OUTPUT FORMAT ───
Return ONLY one JSON object. No markdown.

{
  "needs_clarification": true,
  "summary": "≤40字，概括用户想做什么",
  "missing_aspects": ["scope", "duration"],
  "questions": [
    {
      "id": "scope",
      "prompt": "向用户展示的中文问题，一句话",
      "hint": "输入框占位提示，给例子",
      "required": true
    }
  ],
  "confidence": 0.0
}

─── WHEN needs_clarification SHOULD BE true ───
Set true if ANY of these are unclear and would materially change scheduling:
- **scope** — what exactly to do (e.g. only "高数作业" without chapters/exercises/type)
- **duration** — no explicit or strongly inferable time cost (avoid guessing 30min for heavy work)
- **deadline** — no time limit when one is implied (exception: user gave exact time like 23:59)
- **environment** — strict location/device needs mentioned vaguely ("去个安静地方")
- **dependencies** — multi-step workflow hinted but order unclear
- **split** — one utterance likely hides multiple tasks but boundaries unclear

─── WHEN needs_clarification SHOULD BE false ───
- User gave workable duration (e.g. "两小时", "90分钟", "一下午")
- User gave concrete scope (e.g. "第3章习题1-10", "实验报告第三章")
- User gave explicit DDL (今晚23:59, 明天下午三点前)
- Short but complete micro-tasks ("回复项目组邮件，15分钟")

─── QUESTION RULES ───
- Ask at most 4 questions; prefer 1–3 highly valuable ones.
- Use conversational Chinese; be specific, not generic.
- Each question must have stable snake_case `id`.
- `required` true only for must-have fields (usually scope and/or duration).
- Do NOT ask what user already stated.
- If deadline is clear, do not ask deadline again.

─── EXAMPLES ───
Input: "我今晚要写高数作业，今晚23:59截止"
→ needs_clarification: true; ask scope + duration (homework content and effort unknown)

Input: "明天下午三点前提交实验报告第三章，大概需要2小时，要安静"
→ needs_clarification: false

─── confidence ───
0.85+ if decision is obvious; lower if borderline.
""".strip()


class TaskClarificationAgent:
    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self._llm = llm_client or DeepSeekLLMClient.from_env()

    def assess(
        self,
        user_text: str,
        profile: UserProfile,
        now: datetime,
        existing_tasks: Iterable[Task] = (),
    ) -> Dict[str, Any]:
        payload = {
            "mode": "task_clarification",
            "now": now.isoformat(),
            "user_text": user_text,
            "existing_tasks": [
                {
                    "task_id": task.task_id,
                    "title": task.title,
                    "deadline": task.deadline.isoformat(),
                    "status": task.status.value,
                }
                for task in existing_tasks
            ],
            "profile": {
                "chronotype": profile.chronotype,
                "max_daily_deep_work_min": profile.max_daily_deep_work_min,
            },
        }
        raw = self._llm.generate_json(system_prompt=SYSTEM_PROMPT, payload=payload)
        return normalize_assessment(raw, user_text)

    @staticmethod
    def merge_user_answers(
        original_text: str,
        questions: List[Dict[str, Any]],
        answers: Dict[str, str],
    ) -> str:
        lines = [original_text.strip()]
        answered = []
        for question in questions:
            question_id = str(question.get("id", "")).strip()
            answer = str(answers.get(question_id, "")).strip()
            if answer:
                answered.append((question, answer))
        if not answered:
            return lines[0]
        lines.append("")
        lines.append("【用户补充信息】")
        for question, answer in answered:
            prompt = str(question.get("prompt", question.get("id", "补充"))).strip()
            lines.append(f"- {prompt} {answer}")
        return "\n".join(lines)


def normalize_assessment(raw: Dict[str, Any], user_text: str) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        raw = heuristic_assessment(user_text)
    questions = normalize_questions(raw.get("questions"))
    needs = bool(raw.get("needs_clarification")) and bool(questions)
    if not needs:
        questions = []
    return {
        "needs_clarification": needs,
        "summary": str(raw.get("summary") or user_text[:40]).strip(),
        "missing_aspects": normalize_string_list(raw.get("missing_aspects")),
        "questions": questions,
        "confidence": clamp_confidence(raw.get("confidence")),
    }


def normalize_questions(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    questions: List[Dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            continue
        question_id = str(item.get("id") or f"q{index + 1}").strip()
        prompt = str(item.get("prompt") or "").strip()
        if not prompt:
            continue
        questions.append(
            {
                "id": question_id,
                "prompt": prompt,
                "hint": str(item.get("hint") or "").strip(),
                "required": bool(item.get("required", True)),
            }
        )
    return questions[:4]


def normalize_string_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def clamp_confidence(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.5


def heuristic_assessment(user_text: str) -> Dict[str, Any]:
    text = user_text.strip()
    lower = text.lower()
    has_duration = any(
        token in text or token in lower
        for token in (
            "分钟",
            "小时",
            "点半",
            "min",
            "hour",
            "h",
            "一会儿",
            "半天",
            "一上午",
            "一下午",
            "一晚",
        )
    ) or bool(re.search(r"\d+\s*(分钟|分|小时|h)", text, flags=re.I))
    has_scope_hint = any(
        token in text
        for token in ("第", "章", "节", "题", "页", "报告", "实验", "论文", "邮件", "复习", "背诵")
    )
    vague_homework = any(token in text for token in ("作业", "高数", "数学", "英语", "物理")) and not has_scope_hint
    very_short = len(text) < 18

    questions: List[Dict[str, Any]] = []
    missing: List[str] = []
    if vague_homework or (very_short and not has_duration):
        missing.append("scope")
        questions.append(
            {
                "id": "scope",
                "prompt": "这次任务具体要做哪些内容？",
                "hint": "例如：第3章习题 1-10、两道证明题",
                "required": True,
            }
        )
    if not has_duration:
        missing.append("duration")
        questions.append(
            {
                "id": "duration",
                "prompt": "你预计大概需要多长时间？",
                "hint": "例如：90分钟、大概两小时",
                "required": True,
            }
        )

    needs = bool(questions) and (vague_homework or not has_duration or very_short)
    return {
        "needs_clarification": needs,
        "summary": text[:40] or "新任务",
        "missing_aspects": missing,
        "questions": questions[:4] if needs else [],
        "confidence": 0.55,
    }
