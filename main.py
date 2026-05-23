from __future__ import annotations

from datetime import datetime, time, timedelta

from agents import LocalSeriesAgent, ScoringAgent
from algorithms import WeightedScheduler
from models import Task, UserProfile, UserWeights


def build_profile() -> UserProfile:
    energy_curve = {
        8: 0.55,
        9: 0.78,
        10: 0.9,
        11: 0.86,
        14: 0.68,
        15: 0.74,
        16: 0.7,
        19: 0.62,
        20: 0.76,
        21: 0.72,
    }
    return UserProfile(
        user_id="demo_user",
        chronotype="morning",
        energy_curve=energy_curve,
        available_windows=((time(8, 30), time(12, 0)), (time(14, 0), time(17, 30)), (time(19, 0), time(22, 0))),
        quiet_windows=((time(9, 0), time(11, 30)), (time(20, 0), time(22, 0))),
        max_daily_deep_work_min=150,
        preferred_environments=("desk", "library"),
        weights=UserWeights(lateness=3.2, cognitive_fit=1.5, context_switch=0.7, fragmentation=0.8, preference_match=1.0),
    )


def build_tasks(now: datetime) -> list[Task]:
    return [
        Task(
            task_id="math-review",
            title="高数复习",
            description="复习多元函数微分与典型题，明天测验前必须完成。",
            duration_min=100,
            deadline=now + timedelta(days=1, hours=2),
            earliest_start=now,
            series_id="calculus",
            required_environment=("library",),
            required_quietness=0.75,
            tags=("calculus", "review"),
        ),
        Task(
            task_id="math-homework",
            title="高数作业",
            description="完成课后证明题，需要在复习之后做。",
            duration_min=75,
            deadline=now + timedelta(days=1, hours=8),
            series_id="calculus",
            required_environment=("desk",),
            required_quietness=0.65,
            dependencies=("math-review",),
            tags=("calculus", "homework"),
        ),
        Task(
            task_id="email-reply",
            title="回复邮件",
            description="回复项目组同步邮件，确认今晚会议材料。",
            duration_min=25,
            deadline=now + timedelta(hours=6),
            required_quietness=0.2,
            tags=("email",),
        ),
        Task(
            task_id="essay-draft",
            title="论文初稿",
            description="整理研究动机并写出第一版结构。",
            duration_min=90,
            deadline=now + timedelta(days=2),
            required_environment=("desk",),
            required_quietness=0.8,
            tags=("writing", "research"),
        ),
    ]


def print_scores(scores) -> None:
    print("\n=== Agent Score Matrix ===")
    for task_id, score in scores.items():
        print(
            f"{task_id:<14} "
            f"U={score.urgency:.2f} C={score.complexity:.2f} "
            f"L={score.cognitive_load:.2f} B={score.block_integrity:.2f} "
            f"Q={score.quietness_need:.2f} conf={score.confidence:.2f}"
        )


def print_schedule(title: str, result) -> None:
    print(f"\n=== {title} ===")
    for block in result.blocks:
        print(
            f"{block.start:%m-%d %H:%M} - {block.end:%H:%M} | "
            f"{block.title:<8} | priority={block.priority:.2f} | {block.reason}"
        )
    if result.unscheduled_task_ids:
        print(f"Unscheduled: {', '.join(result.unscheduled_task_ids)}")
    print(f"total_cost={result.total_cost:.4f}")


def main() -> None:
    now = datetime.now().replace(hour=8, minute=20, second=0, microsecond=0)
    profile = build_profile()
    tasks = build_tasks(now)

    scorer = ScoringAgent(ensemble_size=3)
    local_agent = LocalSeriesAgent()
    scheduler = WeightedScheduler()

    scores = scorer.score_tasks(tasks, profile, now)
    locally_ordered = local_agent.order_tasks(tasks, scores, profile)
    schedule = scheduler.schedule(locally_ordered, scores, profile, now)

    print_scores(scores)
    print_schedule("Initial Global Schedule", schedule)

    recovery_now = now + timedelta(hours=3)
    recovery = scheduler.recover_after_miss(
        missed_task_id="math-review",
        tasks=tasks,
        scores=scores,
        profile=profile,
        now=recovery_now,
    )
    print_schedule("Dynamic Cascading Recovery after missing math-review", recovery)


if __name__ == "__main__":
    main()
