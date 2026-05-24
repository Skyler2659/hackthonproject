from __future__ import annotations

import re
from datetime import timedelta
from typing import Iterable

from core.models import ScheduleBlock, Task, TaskScore


PHYSICAL_TOKENS = ("跑步", "运动", "健身", "锻炼", "游泳", "球", "操场", "体测", "骑车")
RECOVERY_TOKENS = ("吃饭", "午饭", "晚饭", "洗澡", "通勤", "赶路", "休息")
COGNITIVE_TOKENS = (
    "学习",
    "复习",
    "写作",
    "报告",
    "论文",
    "作业",
    "数学",
    "物理",
    "英语",
    "编程",
    "代码",
    "阅读",
    "刷题",
)
CONTINUATION_TOKENS = ("单词", "四级", "六级", "词汇", "背诵", "默写", "听力", "同一套")


def transition_buffer_min(previous: Task | None, next_task: Task | None) -> int:
    """Semantic minimum gap between two adjacent tasks.

    This is a lightweight reasonableness reviewer layered on top of CP-SAT. It only
    enforces gaps for transitions that are clearly unrealistic without a pause.
    Similar micro-study tasks, such as vocabulary followed by vocabulary practice,
    are allowed to remain adjacent.
    """
    if previous is None or next_task is None:
        return 0
    if is_continuation_pair(previous, next_task):
        return 0
    previous_text = task_text(previous)
    next_text = task_text(next_task)
    if has_any(previous_text, PHYSICAL_TOKENS) and has_any(next_text, COGNITIVE_TOKENS):
        return 30
    if has_any(previous_text, RECOVERY_TOKENS) or has_any(next_text, RECOVERY_TOKENS):
        return 10
    if context_switch_is_heavy(previous, next_task):
        return 10
    return 0


def is_continuation_pair(previous: Task, next_task: Task) -> bool:
    if previous.series_id and previous.series_id == next_task.series_id:
        return True
    previous_text = task_text(previous)
    next_text = task_text(next_task)
    return has_any(previous_text, CONTINUATION_TOKENS) and has_any(next_text, CONTINUATION_TOKENS)


def context_switch_is_heavy(previous: Task, next_task: Task) -> bool:
    if set(previous.required_environment) != set(next_task.required_environment):
        return True
    return previous.required_quietness >= 0.75 or next_task.required_quietness >= 0.75


def effective_deep_work_min(task: Task, score: TaskScore | None = None) -> int:
    """Minutes of sustained deep focus inside this task block (not the full block duration)."""
    if task.deep_work_min is not None:
        return max(0, min(int(task.deep_work_min), task.duration_min))

    text = task_text(task)
    duration = task.duration_min

    if has_any(text, PHYSICAL_TOKENS) or has_any(
        text, ("跑步", "运动", "健身", "游泳", "球类", "体测", "骑车", "锻炼")
    ):
        return 0
    if has_any(text, ("会议", "开会", "上课", "实验课", "预约", "吃饭", "邮件", "回复", "打卡", "填表")):
        return 0
    if has_any(text, ("背单词", "单词", "四级词汇", "默写", "打卡")) and (
        score is None or score.cognitive_load < 0.85
    ):
        return 0

    if has_any(text, ("kv cache", "kvcache", "kv缓存", "kv 缓存")):
        return duration
    if has_any(text, ("作业", "homework")) and has_any(
        text, ("高数", "数学", "微积分", "线代", "概率", "calculus", "algebra")
    ):
        return min(duration, max(15, duration // 4))
    if has_any(text, ("实验报告", "实验", "lab report", "lab")) and has_any(
        text, ("报告", "撰写", "写作", "写")
    ):
        return min(duration, max(30, duration // 2))
    if has_any(text, ("论文", "编程", "代码", "架构", "证明", "研究", "设计")):
        if score and score.cognitive_load >= 0.88:
            return duration
        return min(duration, max(30, int(duration * 0.7)))

    if score is not None:
        if score.cognitive_load < 0.35:
            return 0
        if score.cognitive_load >= 0.82 and score.block_integrity >= 0.72:
            return duration
        if score.cognitive_load >= 0.55:
            return min(duration, max(10, int(duration * score.cognitive_load * 0.75)))

    if task.must_be_contiguous and duration >= 45:
        return min(duration, max(20, int(duration * 0.4)))
    return 0


def is_deep_work_task(task: Task, score: TaskScore) -> bool:
    return effective_deep_work_min(task, score) > 0


def blocks_have_required_buffer(
    previous_block: ScheduleBlock,
    next_block: ScheduleBlock,
    task_by_id: dict[str, Task],
) -> bool:
    previous = task_by_id.get(previous_block.task_id)
    next_task = task_by_id.get(next_block.task_id)
    required = transition_buffer_min(previous, next_task)
    if required <= 0:
        return True
    return next_block.start >= previous_block.end + timedelta(minutes=required)


def task_text(task: Task) -> str:
    return " ".join(
        item
        for item in (
            task.title,
            task.description,
            " ".join(task.tags),
            task.series_id or "",
        )
        if item
    )


def has_any(text: str, tokens: Iterable[str]) -> bool:
    return any(token in text for token in tokens)


def normalized_terms(text: str) -> set[str]:
    return {item for item in re.split(r"\W+", text.lower()) if item}
