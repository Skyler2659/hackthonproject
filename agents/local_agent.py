from __future__ import annotations

from collections import defaultdict, deque
from typing import Dict, Iterable, List

from models import Task, TaskScore, UserProfile


class LocalSeriesAgent:
    """Coordinates semantically related series before global scheduling."""

    def order_tasks(
        self,
        tasks: Iterable[Task],
        scores: Dict[str, TaskScore],
        profile: UserProfile,
    ) -> List[Task]:
        grouped: Dict[str, List[Task]] = defaultdict(list)
        standalone: List[Task] = []

        for task in tasks:
            if task.series_id:
                grouped[task.series_id].append(task)
            else:
                standalone.append(task)

        ordered: List[Task] = []
        for series_tasks in grouped.values():
            ordered.extend(self._topological_order(series_tasks, scores, profile))

        ordered.extend(
            sorted(
                standalone,
                key=lambda task: (
                    task.deadline,
                    -scores[task.task_id].priority(profile.weights),
                ),
            )
        )
        return ordered

    def _topological_order(
        self,
        tasks: List[Task],
        scores: Dict[str, TaskScore],
        profile: UserProfile,
    ) -> List[Task]:
        by_id = {task.task_id: task for task in tasks}
        indegree = {task.task_id: 0 for task in tasks}
        children: Dict[str, List[str]] = defaultdict(list)

        for task in tasks:
            for dep in task.dependencies:
                if dep in by_id:
                    indegree[task.task_id] += 1
                    children[dep].append(task.task_id)

        ready = deque(
            sorted(
                [task_id for task_id, degree in indegree.items() if degree == 0],
                key=lambda task_id: self._rank(by_id[task_id], scores, profile),
            )
        )

        result: List[Task] = []
        while ready:
            task_id = ready.popleft()
            result.append(by_id[task_id])
            for child_id in children[task_id]:
                indegree[child_id] -= 1
                if indegree[child_id] == 0:
                    ready.append(child_id)

        if len(result) != len(tasks):
            raise ValueError("cycle detected inside task series")

        return result

    @staticmethod
    def _rank(task: Task, scores: Dict[str, TaskScore], profile: UserProfile) -> tuple:
        return (task.deadline, -scores[task.task_id].priority(profile.weights))
