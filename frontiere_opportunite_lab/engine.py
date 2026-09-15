from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import IntEnum, StrEnum
from typing import Iterable, Mapping, Sequence


class ActorContext(StrEnum):
    PERSONAL = "personal"
    SPACE = "space"


class Priority(IntEnum):
    P0_CRITICAL = 0
    P1_REQUIRED = 1
    P2_TIME_CONSTRAINED = 2
    P3_PROGRESS = 3
    P4_INFORMATION = 4


class Actionability(IntEnum):
    TERMINAL = 0
    BLOCKING = 1
    ACTIONABLE = 2
    WAITING = 3
    ADVICE = 4
    INFORMATION = 5


class DeadlineState(IntEnum):
    OVERDUE = 0
    DUE_TODAY = 1
    FUTURE = 2
    NONE = 3


@dataclass(frozen=True, order=True, slots=True)
class Identity:
    source_domain: str
    source_key: str
    action_key: str
    context_type: str
    context_id: str


@dataclass(frozen=True, order=True, slots=True)
class Performance:
    """All coordinates are costs to minimize; no weighted scalar score exists."""

    deadline_minutes: int
    user_effort_min: int
    cash_cdf: int
    travel_min: int
    elapsed_min: int
    interactions: int
    p0_after: int
    p1_after: int
    p2_after: int
    p3_after: int

    def vector(self) -> tuple[int, ...]:
        return (
            self.deadline_minutes,
            self.user_effort_min,
            self.cash_cdf,
            self.travel_min,
            self.elapsed_min,
            self.interactions,
            self.p0_after,
            self.p1_after,
            self.p2_after,
            self.p3_after,
        )

    def dominates(self, other: "Performance") -> bool:
        a, b = self.vector(), other.vector()
        return all(x <= y for x, y in zip(a, b)) and any(x < y for x, y in zip(a, b))


@dataclass(frozen=True, slots=True)
class Plan:
    key: str
    label: str
    cost: Performance
    feasible: bool = True
    infeasible_reason: str = ""


@dataclass(frozen=True, slots=True)
class Target:
    key: str
    label: str
    identity: Identity
    source_domain: str
    actor_context: ActorContext
    priority: Priority
    actionability: Actionability
    deadline_state: DeadlineState
    mandatory: bool
    plans: tuple[Plan, ...]
    reason_codes: tuple[str, ...] = ()
    active: bool = True


@dataclass(frozen=True, slots=True)
class FrontierPoint:
    target_key: str
    target_label: str
    source_domain: str
    plan_key: str
    plan_label: str
    cost: Performance


@dataclass(frozen=True, slots=True)
class Evaluation:
    primary_attention: Target | None
    primary_action_gate: Target | None
    personal_targets: tuple[Target, ...]
    excluded_space_targets: tuple[str, ...]
    eligible_targets: tuple[Target, ...]
    inaccessible_targets: tuple[str, ...]
    deduplicated_identity_count: int
    local_fronts: Mapping[str, tuple[Plan, ...]]
    screened_targets: tuple[str, ...]
    frontier_points: tuple[FrontierPoint, ...]


def _target_sort_key(target: Target) -> tuple:
    return (
        int(target.priority),
        int(target.actionability),
        int(target.deadline_state),
        0 if target.mandatory else 1,
        target.identity,
        target.key,
    )


def pareto_plans(plans: Iterable[Plan]) -> tuple[Plan, ...]:
    rows = tuple(plan for plan in plans if plan.feasible)
    return tuple(
        plan
        for plan in rows
        if not any(other.cost.dominates(plan.cost) for other in rows if other.key != plan.key)
    )


def lower_bound(plans: Sequence[Plan]) -> Performance:
    rows = [plan.cost.vector() for plan in plans if plan.feasible]
    if not rows:
        raise ValueError("lower_bound requires one feasible plan")
    return Performance(*(min(row[k] for row in rows) for k in range(len(rows[0]))))


def _deduplicate_exact_identity(targets: Sequence[Target]) -> tuple[tuple[Target, ...], int]:
    """Mirror Makolo R2: only exact canonical identity may deduplicate."""
    grouped: dict[Identity, list[Target]] = {}
    for target in targets:
        grouped.setdefault(target.identity, []).append(target)

    merged: list[Target] = []
    duplicates = 0
    for identity in sorted(grouped):
        group = grouped[identity]
        base = sorted(group, key=_target_sort_key)[0]
        unique_plans: dict[str, Plan] = {}
        reasons: set[str] = set()
        for target in group:
            reasons.update(target.reason_codes)
            for plan in target.plans:
                unique_plans.setdefault(plan.key, plan)
        duplicates += len(group) - 1
        merged.append(
            Target(
                key=base.key,
                label=base.label,
                identity=identity,
                source_domain=base.source_domain,
                actor_context=base.actor_context,
                priority=min((t.priority for t in group), key=int),
                actionability=min((t.actionability for t in group), key=int),
                deadline_state=min((t.deadline_state for t in group), key=int),
                mandatory=any(t.mandatory for t in group),
                plans=tuple(unique_plans[k] for k in sorted(unique_plans)),
                reason_codes=tuple(sorted(reasons)),
                active=any(t.active for t in group),
            )
        )
    return tuple(sorted(merged, key=_target_sort_key)), duplicates


def _primary_action(ordered: Sequence[Target]) -> Target | None:
    if not ordered:
        return None
    attention = ordered[0]
    actionable = [target for target in ordered if target.actionability == Actionability.ACTIONABLE]
    if attention.actionability == Actionability.TERMINAL:
        return None
    if attention.actionability == Actionability.BLOCKING:
        return next((target for target in actionable if target.priority <= attention.priority), None)
    return actionable[0] if actionable else None


def _gate_targets(ordered: Sequence[Target], primary_action: Target | None) -> tuple[Target, ...]:
    """R2 semantics stay upstream of Pareto.

    Pareto is only allowed to compare actions that R2 could legitimately promote at
    the same priority and deadline-state tier as the current primary action.
    """
    if not ordered or primary_action is None:
        return ()
    attention = ordered[0]
    if attention.actionability == Actionability.TERMINAL:
        return ()
    priority = primary_action.priority
    same_priority = [
        target
        for target in ordered
        if target.actionability == Actionability.ACTIONABLE and target.priority == priority
    ]
    if not same_priority:
        return ()
    deadline_state = min(target.deadline_state for target in same_priority)
    return tuple(target for target in same_priority if target.deadline_state == deadline_state)


def safe_screened_targets(
    targets: Sequence[Target], fronts: Mapping[str, Sequence[Plan]]
) -> tuple[str, ...]:
    """Exact for the supplied finite plan sets: witness dominates component lower bound."""
    screened: list[str] = []
    for target in targets:
        feasible = [p for p in target.plans if p.feasible]
        if not feasible:
            continue
        ell = lower_bound(feasible)
        witnesses = [
            plan.cost
            for other in targets
            if other.key != target.key
            for plan in fronts.get(other.key, ())
        ]
        if any(witness.dominates(ell) for witness in witnesses):
            screened.append(target.key)
    return tuple(sorted(screened))


def global_frontier(
    targets: Sequence[Target], fronts: Mapping[str, Sequence[Plan]]
) -> tuple[FrontierPoint, ...]:
    points = [
        FrontierPoint(
            target.key,
            target.label,
            target.source_domain,
            plan.key,
            plan.label,
            plan.cost,
        )
        for target in targets
        for plan in fronts.get(target.key, ())
    ]
    return tuple(
        point
        for point in points
        if not any(
            other.cost.dominates(point.cost)
            for other in points
            if (other.target_key, other.plan_key) != (point.target_key, point.plan_key)
        )
    )


def evaluate_targets(raw_targets: Sequence[Target]) -> Evaluation:
    active = tuple(target for target in raw_targets if target.active)
    excluded_space = tuple(sorted(t.key for t in active if t.actor_context == ActorContext.SPACE))
    personal_raw = tuple(t for t in active if t.actor_context == ActorContext.PERSONAL)
    personal, duplicates = _deduplicate_exact_identity(personal_raw)
    ordered = tuple(sorted(personal, key=_target_sort_key))
    attention = ordered[0] if ordered else None
    primary_action = _primary_action(ordered)
    gated = _gate_targets(ordered, primary_action)

    inaccessible = tuple(sorted(t.key for t in gated if not any(p.feasible for p in t.plans)))
    eligible = tuple(t for t in gated if any(p.feasible for p in t.plans))
    fronts = {target.key: pareto_plans(target.plans) for target in eligible}
    screened = safe_screened_targets(eligible, fronts)
    frontier = global_frontier(eligible, fronts)

    frontier_targets = {point.target_key for point in frontier}
    if frontier_targets.intersection(screened):
        raise AssertionError("unsafe screening: a true frontier target was screened")

    return Evaluation(
        primary_attention=attention,
        primary_action_gate=primary_action,
        personal_targets=personal,
        excluded_space_targets=excluded_space,
        eligible_targets=eligible,
        inaccessible_targets=inaccessible,
        deduplicated_identity_count=duplicates,
        local_fronts=fronts,
        screened_targets=screened,
        frontier_points=tuple(sorted(frontier, key=lambda p: (p.target_key, p.plan_key))),
    )


def serialise_performance(performance: Performance) -> dict:
    return asdict(performance)
