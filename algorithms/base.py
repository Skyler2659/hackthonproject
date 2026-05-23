from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Iterable, List

from core.models import ScheduleResult, Task, TaskScore, UserProfile


class BaseScheduler(ABC):
    """Polymorphic scheduler contract for greedy, CP-SAT, or future engines."""

    @abstractmethod
    def schedule(
        self,
        tasks: Iterable[Task],
        scores: Dict[str, TaskScore],
        profile: UserProfile,
        now: datetime,
    ) -> ScheduleResult:
        raise NotImplementedError

    def recover_after_miss(
        self,
        missed_task_id: str,
        tasks: List[Task],
        scores: Dict[str, TaskScore],
        profile: UserProfile,
        now: datetime,
    ) -> ScheduleResult:
        raise NotImplementedError("This scheduler does not implement recovery.")
