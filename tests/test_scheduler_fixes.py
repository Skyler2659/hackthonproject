from __future__ import annotations

from datetime import datetime, time, timedelta

from algorithms import GreedyScheduler, HybridScheduler, WeightedScheduler
from algorithms.task_selection import prepare_schedulable_tasks
from agents.local_agent import LocalSeriesAgent
from llm.mock_client import MockLLMClient
from models import Task, TaskScore, TaskStatus, UserProfile, UserWeights


def build_profile() -> UserProfile:
    return UserProfile(
        user_id="test",
        chronotype="morning",
        energy_curve={hour: 0.7 for hour in range(8, 22)},
        available_windows=((time(8, 0), time(22, 0)),),
        quiet_windows=((time(9, 0), time(11, 0)),),
        max_daily_deep_work_min=180,
        preferred_environments=("desk", "library"),
        weights=UserWeights(),
    )


def build_score(task_id: str) -> TaskScore:
    return TaskScore(
        task_id=task_id,
        urgency=0.7,
        complexity=0.6,
        cognitive_load=0.8,
        block_integrity=0.7,
        quietness_need=0.6,
        confidence=0.9,
        rationale="test",
    ).normalized()


def test_pending_must_finish_before_deadline() -> None:
    now = datetime(2026, 5, 23, 8, 0)
    profile = build_profile()
    task = Task(
        task_id="essay",
        title="essay",
        description="",
        duration_min=60,
        deadline=now + timedelta(hours=4),
        required_environment=("desk",),
    )
    scores = {task.task_id: build_score(task.task_id)}
    result = GreedyScheduler().schedule([task], scores, profile, now)
    assert result.blocks
    assert result.blocks[0].end <= task.deadline


def test_missed_may_use_late_slot() -> None:
    now = datetime(2026, 5, 23, 14, 0)
    profile = build_profile()
    task = Task(
        task_id="late",
        title="late",
        description="",
        duration_min=60,
        deadline=now - timedelta(hours=2),
        status=TaskStatus.MISSED,
    )
    scores = {task.task_id: build_score(task.task_id)}
    result = GreedyScheduler().schedule([task], scores, profile, now)
    assert result.blocks
    assert result.blocks[0].end > task.deadline


def test_recovery_reschedules_all_pending() -> None:
    now = datetime(2026, 5, 23, 8, 0)
    profile = build_profile()
    review = Task(
        task_id="review",
        title="review",
        description="",
        duration_min=60,
        deadline=now + timedelta(days=1),
        status=TaskStatus.MISSED,
    )
    homework = Task(
        task_id="homework",
        title="homework",
        description="",
        duration_min=60,
        deadline=now + timedelta(days=1),
        dependencies=("review",),
    )
    email = Task(
        task_id="email",
        title="email",
        description="",
        duration_min=30,
        deadline=now + timedelta(hours=10),
    )
    scores = {
        homework.task_id: build_score(homework.task_id),
        email.task_id: build_score(email.task_id),
    }
    result = HybridScheduler().recover_after_miss("review", [review, homework, email], scores, profile, now)
    scheduled_ids = {block.task_id for block in result.blocks}
    assert "email" in scheduled_ids
    assert "homework" in scheduled_ids


def test_local_agent_orders_cross_series_dependency() -> None:
    now = datetime(2026, 5, 23, 8, 0)
    profile = build_profile()
    base = Task(
        task_id="base",
        title="base",
        description="",
        duration_min=30,
        deadline=now + timedelta(hours=8),
        series_id="s1",
    )
    child = Task(
        task_id="child",
        title="child",
        description="",
        duration_min=30,
        deadline=now + timedelta(hours=9),
        series_id="s2",
        dependencies=("base",),
    )
    scores = {task.task_id: build_score(task.task_id) for task in (base, child)}
    ordered = LocalSeriesAgent().order_tasks([child, base], scores, profile)
    assert [task.task_id for task in ordered] == ["base", "child"]


def test_prepare_schedulable_tasks_strips_done_dependencies() -> None:
    now = datetime(2026, 5, 23, 8, 0)
    done = Task(
        task_id="done",
        title="done",
        description="",
        duration_min=30,
        deadline=now + timedelta(hours=1),
        status=TaskStatus.DONE,
    )
    pending = Task(
        task_id="next",
        title="next",
        description="",
        duration_min=30,
        deadline=now + timedelta(hours=4),
        dependencies=("done",),
    )
    prepared = prepare_schedulable_tasks([done, pending])
    assert len(prepared) == 1
    assert prepared[0].dependencies == ()


def test_mock_parser_returns_tasks_array() -> None:
    client = MockLLMClient()
    payload = {
        "user_text": "明天晚上前写实验报告，需要安静环境",
        "now": datetime.now().isoformat(),
        "allowed_environment_options": ["desk", "library"],
        "existing_tasks": [],
        "profile": {"max_daily_deep_work_min": 180},
    }
    response = client.generate_json("parser", payload)
    assert isinstance(response.get("tasks"), list)
    assert response["tasks"]


def test_weighted_scheduler_is_hybrid() -> None:
    assert WeightedScheduler is HybridScheduler


if __name__ == "__main__":
    test_pending_must_finish_before_deadline()
    test_missed_may_use_late_slot()
    test_recovery_reschedules_all_pending()
    test_local_agent_orders_cross_series_dependency()
    test_prepare_schedulable_tasks_strips_done_dependencies()
    test_mock_parser_returns_tasks_array()
    test_weighted_scheduler_is_hybrid()
    print("all tests passed")
