from __future__ import annotations

from agents.task_clarification_agent import TaskClarificationAgent, heuristic_assessment, normalize_assessment
from llm.mock_client import MockLLMClient


def test_heuristic_flags_vague_homework() -> None:
    assessment = heuristic_assessment("我今晚要写高数作业，今晚23:59截止")
    assert assessment["needs_clarification"] is True
    assert len(assessment["questions"]) >= 2


def test_heuristic_allows_detailed_task() -> None:
    assessment = heuristic_assessment("明天18点前完成实验报告第三章，大概2小时，要安静")
    assert assessment["needs_clarification"] is False
    assert assessment["questions"] == []


def test_merge_user_answers() -> None:
    original = "我今晚要写高数作业"
    questions = [
        {"id": "scope", "prompt": "具体要做哪些部分？"},
        {"id": "duration", "prompt": "预计多久？"},
    ]
    merged = TaskClarificationAgent.merge_user_answers(
        original,
        questions,
        {"scope": "第3章习题1-10", "duration": "90分钟"},
    )
    assert "第3章习题1-10" in merged
    assert "90分钟" in merged


def test_mock_client_clarification_mode() -> None:
    client = MockLLMClient()
    response = client.generate_json(
        "clarify",
        {
            "mode": "task_clarification",
            "user_text": "我今晚要写高数作业，今晚23:59截止",
            "now": "2026-05-23T18:00:00",
        },
    )
    normalized = normalize_assessment(response, "我今晚要写高数作业，今晚23:59截止")
    assert normalized["needs_clarification"] is True


if __name__ == "__main__":
    test_heuristic_flags_vague_homework()
    test_heuristic_allows_detailed_task()
    test_merge_user_answers()
    test_mock_client_clarification_mode()
    print("all clarification tests passed")
