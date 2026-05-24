from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, time, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple


class TaskStatus(str, Enum):
    PENDING = "pending"
    SCHEDULED = "scheduled"
    MISSED = "missed"
    DONE = "done"
    CANCELLED = "cancelled"


class DeadlineType(str, Enum):
    STRICT = "strict"
    FLEXIBLE = "flexible"


@dataclass(frozen=True)
class UserWeights:
    lateness: float = 3.0
    cognitive_fit: float = 1.4
    context_switch: float = 0.7
    fragmentation: float = 0.8
    preference_match: float = 1.0


@dataclass(frozen=True)
class UserProfile:
    user_id: str
    chronotype: str
    energy_curve: Dict[int, float]
    available_windows: Tuple[Tuple[time, time], ...]
    quiet_windows: Tuple[Tuple[time, time], ...] = field(default_factory=tuple)
    # Questionnaire / lifestyle windows — affect slot cost only, not feasibility (see preferred_windows).
    preferred_windows: Tuple[Tuple[time, time], ...] = field(default_factory=tuple)
    max_daily_deep_work_min: int = 180
    preferred_environments: Tuple[str, ...] = ("desk",)
    weights: UserWeights = field(default_factory=UserWeights)

    def energy_at(self, moment: datetime) -> float:
        return clamp01(self.energy_curve.get(moment.hour, 0.5))

    def quietness_at(self, moment: datetime) -> float:
        current_time = moment.time()
        for start, end in self.quiet_windows:
            if start <= current_time < end:
                return 0.95
        return 0.45


@dataclass(frozen=True)
class Task:
    task_id: str
    title: str
    description: str
    duration_min: int
    deadline: datetime
    earliest_start: Optional[datetime] = None
    series_id: Optional[str] = None
    required_environment: Tuple[str, ...] = field(default_factory=tuple)
    required_quietness: float = 0.0
    dependencies: Tuple[str, ...] = field(default_factory=tuple)
    must_be_contiguous: bool = True
    status: TaskStatus = TaskStatus.PENDING
    tags: Tuple[str, ...] = field(default_factory=tuple)
    deadline_type: DeadlineType = DeadlineType.FLEXIBLE
    manual_start: Optional[datetime] = None
    manual_end: Optional[datetime] = None
    # Sustained deep-focus minutes inside this block (0..duration_min). None → inferred at schedule time.
    deep_work_min: Optional[int] = None

    def with_status(self, status: TaskStatus) -> "Task":
        return replace(self, status=status)


@dataclass(frozen=True)
class TaskScore:
    task_id: str
    urgency: float
    complexity: float
    cognitive_load: float
    block_integrity: float
    quietness_need: float
    confidence: float
    rationale: str
    environment_dependency: float = 0.0
    agent_votes: List[Dict[str, object]] = field(default_factory=list)

    def normalized(self) -> "TaskScore":
        return replace(
            self,
            urgency=clamp01(self.urgency),
            complexity=clamp01(self.complexity),
            cognitive_load=clamp01(self.cognitive_load),
            block_integrity=clamp01(self.block_integrity),
            quietness_need=clamp01(self.quietness_need),
            confidence=clamp01(self.confidence),
            environment_dependency=clamp01(self.environment_dependency),
        )

    def priority(self, weights: UserWeights) -> float:
        raw_priority = (
            self.urgency * weights.lateness
            + self.complexity * 0.8
            + self.cognitive_load * weights.cognitive_fit
            + self.block_integrity * weights.fragmentation
            + self.environment_dependency * weights.preference_match
            + self.quietness_need * weights.preference_match * 0.5
        )
        return raw_priority * self.confidence


@dataclass(frozen=True)
class ScheduleBlock:
    task_id: str
    title: str
    start: datetime
    end: datetime
    priority: float
    reason: str


@dataclass(frozen=True)
class ScheduleResult:
    blocks: List[ScheduleBlock]
    unscheduled_task_ids: List[str]
    total_cost: float


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def minutes(value: int) -> timedelta:
    return timedelta(minutes=value)
