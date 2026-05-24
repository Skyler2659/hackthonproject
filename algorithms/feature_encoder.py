from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple

from algorithms.candidate_slots import CandidateSlot, slot_sort_cost
from algorithms.constants import (
    COST_SCALE,
    UNSCHEDULED_BASE_PENALTY,
)
from algorithms.semantic_rules import effective_deep_work_min
from core.models import Task, TaskScore, UserProfile


@dataclass(frozen=True)
class TaskFeatures:
    task_id: str
    priority: float
    cognitive_load: float
    block_integrity: float
    quietness_need: float
    deep_work_min: int
    unscheduled_penalty: int


@dataclass(frozen=True)
class EncodedSchedule:
    task_features: Dict[str, TaskFeatures]
    slot_costs: Dict[Tuple[str, str], int]


class FeatureEncoder:
    """Turns semantic scores into integer costs for CP-SAT."""

    def encode(
        self,
        tasks: Iterable[Task],
        scores: Dict[str, TaskScore],
        profile: UserProfile,
        candidates: Dict[str, List[CandidateSlot]],
    ) -> EncodedSchedule:
        task_features: Dict[str, TaskFeatures] = {}
        slot_costs: Dict[Tuple[str, str], int] = {}

        for task in tasks:
            raw_score = scores.get(task.task_id)
            if raw_score is None:
                continue
            score = raw_score.normalized()
            priority = score.priority(profile.weights)
            deep_work_min = effective_deep_work_min(task, score)
            task_features[task.task_id] = TaskFeatures(
                task_id=task.task_id,
                priority=priority,
                cognitive_load=score.cognitive_load,
                block_integrity=score.block_integrity,
                quietness_need=max(task.required_quietness, score.quietness_need),
                deep_work_min=deep_work_min,
                unscheduled_penalty=unscheduled_penalty(score, priority),
            )
            for slot in candidates.get(task.task_id, []):
                slot_costs[(task.task_id, slot.slot_id)] = slot_sort_cost(slot, profile)

        return EncodedSchedule(task_features=task_features, slot_costs=slot_costs)


def unscheduled_penalty(score: TaskScore, priority: float) -> int:
    urgency_pressure = score.urgency + score.block_integrity * 0.5 + score.cognitive_load * 0.25
    return int(
        round(
            UNSCHEDULED_BASE_PENALTY
            + priority * COST_SCALE * 20
            + urgency_pressure * COST_SCALE * 20
        )
    )
