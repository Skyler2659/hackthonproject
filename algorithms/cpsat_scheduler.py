from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, Iterable, List, Tuple

from algorithms.base import BaseScheduler
from algorithms.candidate_slots import CandidateSlot, CandidateSlotGenerator
from algorithms.constants import (
    COST_SCALE,
    DEEP_WORK_OVERAGE_COST_PER_MIN,
    DEFAULT_SEARCH_WORKERS,
    DEFAULT_SOLVER_TIME_LIMIT_SEC,
    MAX_CANDIDATE_SLOTS_PER_TASK,
)
from algorithms.feature_encoder import EncodedSchedule, FeatureEncoder
from algorithms.greedy_scheduler import GreedyScheduler
from algorithms.infeasibility import InfeasibilityHandler, InfeasibilityReason
from algorithms.recovery import RecoveryEngine
from algorithms.semantic_rules import transition_buffer_min
from algorithms.task_selection import prepare_schedulable_tasks
from core.models import ScheduleBlock, ScheduleResult, Task, TaskScore, TaskStatus, UserProfile

try:  # pragma: no cover - exercised only when OR-Tools is unavailable.
    from ortools.sat.python import cp_model
except ImportError:  # pragma: no cover
    cp_model = None


class CPSatScheduler(BaseScheduler):
    """CP-SAT scheduler using one optional candidate-slot variable per task slot."""

    def __init__(
        self,
        time_limit_sec: float = DEFAULT_SOLVER_TIME_LIMIT_SEC,
        search_workers: int = DEFAULT_SEARCH_WORKERS,
        max_candidate_slots: int = MAX_CANDIDATE_SLOTS_PER_TASK,
    ) -> None:
        self.time_limit_sec = time_limit_sec
        self.search_workers = search_workers
        self._slot_generator = CandidateSlotGenerator(max_slots_per_task=max_candidate_slots)
        self._feature_encoder = FeatureEncoder()
        self._infeasibility = InfeasibilityHandler()
        self.last_status: str | None = None
        self.last_reasons: List[InfeasibilityReason] = []

    def schedule(
        self,
        tasks: Iterable[Task],
        scores: Dict[str, TaskScore],
        profile: UserProfile,
        now: datetime,
    ) -> ScheduleResult:
        if cp_model is None:
            self.last_status = "ORTOOLS_UNAVAILABLE"
            return GreedyScheduler().schedule(tasks, scores, profile, now)

        active_tasks = [
            task
            for task in prepare_schedulable_tasks(tasks)
            if task.task_id in scores
        ]
        if not active_tasks:
            self.last_status = "EMPTY"
            return ScheduleResult(blocks=[], unscheduled_task_ids=[], total_cost=0.0)

        self.last_reasons = self._infeasibility.preflight(active_tasks, scores, profile, now)
        candidates = self._slot_generator.generate(active_tasks, scores, profile, now)
        encoded = self._feature_encoder.encode(active_tasks, scores, profile, candidates)
        model = cp_model.CpModel()

        x, y, intervals = self._build_variables(model, active_tasks, candidates, now)
        if intervals:
            model.AddNoOverlap(intervals)

        self._add_dependency_constraints(model, active_tasks, candidates, x, y)
        self._add_transition_buffer_constraints(model, active_tasks, candidates, x)
        deep_overage_terms = self._add_deep_work_soft_constraints(
            model, active_tasks, candidates, encoded, x, profile
        )
        self._add_objective(model, active_tasks, candidates, encoded, x, y, deep_overage_terms)

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = self.time_limit_sec
        solver.parameters.num_search_workers = self.search_workers
        status = solver.Solve(model)
        self.last_status = solver.StatusName(status)

        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return materialize_result(active_tasks, candidates, encoded, x, solver)
        if status in (cp_model.UNKNOWN, cp_model.INFEASIBLE):
            if status == cp_model.UNKNOWN:
                self.last_reasons.append(
                    InfeasibilityReason(
                        code="SOLVER_TIMEOUT",
                        task_id=None,
                        message="CP-SAT did not converge before time limit",
                        suggestion="used greedy fallback result",
                    )
                )
            else:
                self.last_reasons.append(
                    InfeasibilityReason(
                        code="CP_INFEASIBLE",
                        task_id=None,
                        message="CP-SAT found no feasible assignment",
                        suggestion="used greedy fallback result",
                    )
                )
            return GreedyScheduler().schedule(active_tasks, scores, profile, now)
        return GreedyScheduler().schedule(active_tasks, scores, profile, now)

    def _build_variables(
        self,
        model: "cp_model.CpModel",
        tasks: List[Task],
        candidates: Dict[str, List[CandidateSlot]],
        now: datetime,
    ) -> tuple[
        Dict[Tuple[str, str], "cp_model.IntVar"],
        Dict[str, "cp_model.IntVar"],
        List["cp_model.IntervalVar"],
    ]:
        origin = planning_origin(tasks, candidates, now)
        x: Dict[Tuple[str, str], "cp_model.IntVar"] = {}
        y: Dict[str, "cp_model.IntVar"] = {}
        intervals: List["cp_model.IntervalVar"] = []

        for task in tasks:
            y[task.task_id] = model.NewBoolVar(f"scheduled_{safe_name(task.task_id)}")
            slot_vars = []
            for slot in candidates.get(task.task_id, []):
                var = model.NewBoolVar(f"x_{safe_name(task.task_id)}_{slot.start:%Y%m%d%H%M}")
                x[(task.task_id, slot.slot_id)] = var
                slot_vars.append(var)
                start = minutes_from_origin(slot.start, origin)
                end = minutes_from_origin(slot.end, origin)
                intervals.append(
                    model.NewOptionalIntervalVar(
                        start,
                        task.duration_min,
                        end,
                        var,
                        f"interval_{safe_name(task.task_id)}_{slot.start:%Y%m%d%H%M}",
                    )
                )
            if slot_vars:
                model.Add(sum(slot_vars) == y[task.task_id])
                if task.manual_start is not None and task.manual_end is not None:
                    model.Add(y[task.task_id] == 1)
            else:
                model.Add(y[task.task_id] == 0)
        return x, y, intervals

    def _add_dependency_constraints(
        self,
        model: "cp_model.CpModel",
        tasks: List[Task],
        candidates: Dict[str, List[CandidateSlot]],
        x: Dict[Tuple[str, str], "cp_model.IntVar"],
        y: Dict[str, "cp_model.IntVar"],
    ) -> None:
        task_ids = {task.task_id for task in tasks}
        for task in tasks:
            child_slots = candidates.get(task.task_id, [])
            for parent_id in task.dependencies:
                if parent_id not in task_ids:
                    continue
                if not candidates.get(parent_id):
                    model.Add(y[task.task_id] == 0)
                    continue
                model.Add(y[task.task_id] <= y[parent_id])
                for parent_slot in candidates[parent_id]:
                    for child_slot in child_slots:
                        if parent_slot.end > child_slot.start:
                            model.Add(
                                x[(parent_id, parent_slot.slot_id)]
                                + x[(task.task_id, child_slot.slot_id)]
                                <= 1
                            )

    def _add_transition_buffer_constraints(
        self,
        model: "cp_model.CpModel",
        tasks: List[Task],
        candidates: Dict[str, List[CandidateSlot]],
        x: Dict[Tuple[str, str], "cp_model.IntVar"],
    ) -> None:
        task_by_id = {task.task_id: task for task in tasks}
        task_ids = list(candidates)
        for left_index, left_id in enumerate(task_ids):
            left_task = task_by_id[left_id]
            for right_id in task_ids[left_index + 1 :]:
                right_task = task_by_id[right_id]
                for left_slot in candidates.get(left_id, []):
                    for right_slot in candidates.get(right_id, []):
                        if violates_transition_buffer(left_task, left_slot, right_task, right_slot):
                            model.Add(
                                x[(left_id, left_slot.slot_id)]
                                + x[(right_id, right_slot.slot_id)]
                                <= 1
                            )

    def _add_deep_work_soft_constraints(
        self,
        model: "cp_model.CpModel",
        tasks: List[Task],
        candidates: Dict[str, List[CandidateSlot]],
        encoded: EncodedSchedule,
        x: Dict[Tuple[str, str], "cp_model.IntVar"],
        profile: UserProfile,
    ) -> List["cp_model.IntVar"]:
        if profile.max_daily_deep_work_min <= 0:
            return []
        task_by_id = {task.task_id: task for task in tasks}
        terms_by_day = defaultdict(list)
        for task_id, slots in candidates.items():
            features = encoded.task_features[task_id]
            if features.deep_work_min <= 0:
                continue
            for slot in slots:
                terms_by_day[slot.start.date()].append(
                    features.deep_work_min * x[(task_id, slot.slot_id)]
                )
        overage_terms = []
        for day, terms in terms_by_day.items():
            if terms:
                upper_bound = sum(
                    task_by_id[task_id].duration_min
                    for task_id, slots in candidates.items()
                    if any(slot.start.date() == day for slot in slots)
                )
                overage = model.NewIntVar(0, max(0, upper_bound), f"deep_overage_{day:%Y%m%d}")
                model.Add(sum(terms) <= profile.max_daily_deep_work_min + overage)
                overage_terms.append(overage)
        return overage_terms

    def _add_objective(
        self,
        model: "cp_model.CpModel",
        tasks: List[Task],
        candidates: Dict[str, List[CandidateSlot]],
        encoded: EncodedSchedule,
        x: Dict[Tuple[str, str], "cp_model.IntVar"],
        y: Dict[str, "cp_model.IntVar"],
        deep_overage_terms: List["cp_model.IntVar"] | None = None,
    ) -> None:
        objective_terms = []
        for task in tasks:
            features = encoded.task_features[task.task_id]
            objective_terms.append(features.unscheduled_penalty * (1 - y[task.task_id]))
            for slot in candidates.get(task.task_id, []):
                cost = encoded.slot_costs[(task.task_id, slot.slot_id)]
                objective_terms.append(cost * x[(task.task_id, slot.slot_id)])
        for overage in deep_overage_terms or []:
            objective_terms.append(DEEP_WORK_OVERAGE_COST_PER_MIN * overage)
        model.Minimize(sum(objective_terms))


class HybridScheduler(BaseScheduler):
    """Primary CP-SAT scheduler with deterministic greedy fallback."""

    def __init__(
        self,
        time_limit_sec: float = DEFAULT_SOLVER_TIME_LIMIT_SEC,
        search_workers: int = DEFAULT_SEARCH_WORKERS,
        max_candidate_slots: int = MAX_CANDIDATE_SLOTS_PER_TASK,
    ) -> None:
        self._cpsat = CPSatScheduler(
            time_limit_sec=time_limit_sec,
            search_workers=search_workers,
            max_candidate_slots=max_candidate_slots,
        )
        self._greedy = GreedyScheduler()
        self._recovery = RecoveryEngine()
        self.last_status: str | None = None
        self.last_reasons: List[InfeasibilityReason] = []

    def schedule(
        self,
        tasks: Iterable[Task],
        scores: Dict[str, TaskScore],
        profile: UserProfile,
        now: datetime,
    ) -> ScheduleResult:
        result = self._cpsat.schedule(tasks, scores, profile, now)
        self.last_status = self._cpsat.last_status
        self.last_reasons = list(self._cpsat.last_reasons)
        return result

    def recover_after_miss(
        self,
        missed_task_id: str,
        tasks: List[Task],
        scores: Dict[str, TaskScore],
        profile: UserProfile,
        now: datetime,
    ) -> ScheduleResult:
        self._recovery.affected_task_ids(missed_task_id, tasks, now)
        return self.schedule(
            prepare_schedulable_tasks(tasks),
            scores,
            profile,
            now,
        )


def materialize_result(
    tasks: List[Task],
    candidates: Dict[str, List[CandidateSlot]],
    encoded: EncodedSchedule,
    x: Dict[Tuple[str, str], "cp_model.IntVar"],
    solver: "cp_model.CpSolver",
) -> ScheduleResult:
    task_by_id = {task.task_id: task for task in tasks}
    blocks: List[ScheduleBlock] = []
    scheduled_ids = set()

    for task_id, slots in candidates.items():
        for slot in slots:
            if solver.BooleanValue(x[(task_id, slot.slot_id)]):
                task = task_by_id[task_id]
                features = encoded.task_features[task_id]
                scheduled_ids.add(task_id)
                blocks.append(
                    ScheduleBlock(
                        task_id=task.task_id,
                        title=task.title,
                        start=slot.start,
                        end=slot.end,
                        priority=features.priority,
                        reason=cp_sat_reason(slot, encoded.slot_costs[(task_id, slot.slot_id)]),
                    )
                )
                break

    blocks.sort(key=lambda block: block.start)
    unscheduled = sorted(task.task_id for task in tasks if task.task_id not in scheduled_ids)
    return ScheduleResult(
        blocks=blocks,
        unscheduled_task_ids=unscheduled,
        total_cost=round(float(solver.ObjectiveValue()) / COST_SCALE, 4),
    )


def violates_transition_buffer(
    left_task: Task,
    left_slot: CandidateSlot,
    right_task: Task,
    right_slot: CandidateSlot,
) -> bool:
    if left_slot.end <= right_slot.start:
        required = transition_buffer_min(left_task, right_task)
        return required > 0 and right_slot.start < left_slot.end + timedelta(minutes=required)
    if right_slot.end <= left_slot.start:
        required = transition_buffer_min(right_task, left_task)
        return required > 0 and left_slot.start < right_slot.end + timedelta(minutes=required)
    return False


def cp_sat_reason(slot: CandidateSlot, slot_cost: int) -> str:
    lateness = slot.cost_lateness / COST_SCALE
    cognitive = slot.cost_cognitive / COST_SCALE
    quiet = slot.cost_quiet / COST_SCALE
    return (
        f"CP-SAT全局排程；精力={slot.energy:.2f}, 安静度={slot.quietness:.2f}, "
        f"认知差={cognitive:.2f}, 安静缺口={quiet:.2f}, "
        f"延迟小时={lateness:.2f}, 槽成本={slot_cost / COST_SCALE:.2f}"
    )


def planning_origin(
    tasks: List[Task],
    candidates: Dict[str, List[CandidateSlot]],
    now: datetime | None = None,
) -> datetime:
    starts = [slot.start for slots in candidates.values() for slot in slots]
    starts.extend(task.earliest_start for task in tasks if task.earliest_start is not None)
    starts.extend(task.deadline for task in tasks)
    if now is not None:
        starts.append(now)
    if not starts:
        return now or datetime.now().replace(second=0, microsecond=0)
    return min(starts)


def minutes_from_origin(moment: datetime, origin: datetime) -> int:
    return int((moment - origin).total_seconds() // 60)


def safe_name(value: str) -> str:
    return "".join(char if char.isalnum() else "_" for char in value)


WeightedScheduler = HybridScheduler
