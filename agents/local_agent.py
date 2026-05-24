from __future__ import annotations

from collections import defaultdict, deque
from typing import Dict, Iterable, List

from models import Task, TaskScore, UserProfile


class LocalSeriesAgent:
    """Orders tasks respecting dependencies across the full pending set."""

    def order_tasks(
        self,
        tasks: Iterable[Task],
        scores: Dict[str, TaskScore],
        profile: UserProfile,
    ) -> List[Task]:
        task_list = list(tasks)
        if not task_list:
            return []
        return self._topological_order(task_list, scores, profile)

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
            for child_id in sorted(
                children[task_id],
                key=lambda cid: self._rank(by_id[cid], scores, profile),
            ):
                indegree[child_id] -= 1
                if indegree[child_id] == 0:
                    ready.append(child_id)

        if len(result) != len(tasks):
            raise ValueError("cycle detected in task dependencies")

        return result

    @staticmethod
    def _rank(task: Task, scores: Dict[str, TaskScore], profile: UserProfile) -> tuple:
        score = scores.get(task.task_id)
        priority = score.priority(profile.weights) if score else 0.0
        return (task.deadline, -priority)
