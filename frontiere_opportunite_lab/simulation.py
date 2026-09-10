from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from enum import Enum, IntEnum
from json import dumps
from pathlib import Path
from typing import Iterable, Mapping, Sequence


class ActorContext(str, Enum):
    PERSONAL = "personal"
    SPACE = "space"


class Priority(IntEnum):
    P0_CRITICAL = 0
    P1_REQUIRED = 1
    P2_TIME_CONSTRAINED = 2
    P3_PROGRESS = 3
    P4_INFORMATION = 4


@dataclass(frozen=True, order=True, slots=True)
class Performance:
    user_minutes: int
    cash_cents: int
    travel_minutes: int
    steps_remaining: int

    def dominates(self, other: "Performance") -> bool:
        a = (self.user_minutes, self.cash_cents, self.travel_minutes, self.steps_remaining)
        b = (other.user_minutes, other.cash_cents, other.travel_minutes, other.steps_remaining)
        return all(x <= y for x, y in zip(a, b)) and any(x < y for x, y in zip(a, b))


@dataclass(frozen=True, slots=True)
class Plan:
    key: str
    label: str
    cost: Performance
    feasible: bool = True


@dataclass(frozen=True, slots=True)
class Target:
    key: str
    source_domain: str
    label: str
    actor_context: ActorContext
    priority: Priority
    plans: tuple[Plan, ...]
    active: bool = True
    reason: str = ""


@dataclass(frozen=True, slots=True)
class PersonalState:
    tick: int
    profile_key: str
    targets: tuple[Target, ...]


@dataclass(frozen=True, slots=True)
class FrontierPoint:
    target_key: str
    target_label: str
    source_domain: str
    plan_key: str
    plan_label: str
    cost: Performance


@dataclass(frozen=True, slots=True)
class Snapshot:
    tick: int
    active_personal_targets: tuple[str, ...]
    excluded_space_targets: tuple[str, ...]
    gate_priority: str | None
    local_front_sizes: Mapping[str, int]
    screened_targets: tuple[str, ...]
    frontier_targets: tuple[str, ...]
    frontier_points: tuple[FrontierPoint, ...]


def pareto_plans(plans: Iterable[Plan]) -> tuple[Plan, ...]:
    rows = tuple(plan for plan in plans if plan.feasible)
    return tuple(
        plan
        for plan in rows
        if not any(other.cost.dominates(plan.cost) for other in rows if other.key != plan.key)
    )


def lower_bound(plans: Sequence[Plan]) -> Performance:
    rows = [p.cost for p in plans if p.feasible]
    if not rows:
        raise ValueError("lower_bound requires at least one feasible plan")
    return Performance(
        min(p.user_minutes for p in rows),
        min(p.cash_cents for p in rows),
        min(p.travel_minutes for p in rows),
        min(p.steps_remaining for p in rows),
    )


def personal_candidates(state: PersonalState) -> tuple[Target, ...]:
    return tuple(
        target
        for target in state.targets
        if target.active and target.actor_context is ActorContext.PERSONAL and any(p.feasible for p in target.plans)
    )


def gated_candidates(state: PersonalState) -> tuple[Target, ...]:
    candidates = personal_candidates(state)
    if not candidates:
        return ()
    priority = min(target.priority for target in candidates)
    return tuple(target for target in candidates if target.priority == priority)


def local_fronts(targets: Sequence[Target]) -> dict[str, tuple[Plan, ...]]:
    return {target.key: pareto_plans(target.plans) for target in targets}


def safe_screened_targets(targets: Sequence[Target], fronts: Mapping[str, Sequence[Plan]]) -> tuple[str, ...]:
    screened: list[str] = []
    for target in targets:
        ell = lower_bound(target.plans)
        witnesses = [
            plan.cost
            for other in targets
            if other.key != target.key
            for plan in fronts[other.key]
        ]
        if any(witness.dominates(ell) for witness in witnesses):
            screened.append(target.key)
    return tuple(sorted(screened))


def global_frontier(targets: Sequence[Target], fronts: Mapping[str, Sequence[Plan]]) -> tuple[FrontierPoint, ...]:
    points = [
        FrontierPoint(target.key, target.label, target.source_domain, plan.key, plan.label, plan.cost)
        for target in targets
        for plan in fronts[target.key]
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


def evaluate(state: PersonalState) -> Snapshot:
    personal = personal_candidates(state)
    excluded = tuple(sorted(t.key for t in state.targets if t.active and t.actor_context is ActorContext.SPACE))
    gated = gated_candidates(state)
    fronts = local_fronts(gated)
    screened = safe_screened_targets(gated, fronts) if gated else ()
    frontier = global_frontier(gated, fronts) if gated else ()

    frontier_targets = {point.target_key for point in frontier}
    if frontier_targets.intersection(screened):
        raise AssertionError("unsafe screening: a frontier target was screened")

    return Snapshot(
        tick=state.tick,
        active_personal_targets=tuple(sorted(t.key for t in personal)),
        excluded_space_targets=excluded,
        gate_priority=(min(t.priority for t in gated).name if gated else None),
        local_front_sizes={key: len(value) for key, value in sorted(fronts.items())},
        screened_targets=screened,
        frontier_targets=tuple(sorted(frontier_targets)),
        frontier_points=tuple(sorted(frontier, key=lambda p: (p.target_key, p.plan_key))),
    )


def resolve_targets(state: PersonalState, *keys: str) -> PersonalState:
    resolved = set(keys)
    return PersonalState(
        tick=state.tick + 1,
        profile_key=state.profile_key,
        targets=tuple(replace(t, active=False) if t.key in resolved else t for t in state.targets),
    )


def p(key: str, label: str, minutes: int, cents: int, travel: int, steps: int) -> Plan:
    return Plan(key, label, Performance(minutes, cents, travel, steps))


def target(
    key: str,
    domain: str,
    label: str,
    context: ActorContext,
    priority: Priority,
    plans: Sequence[Plan],
    reason: str,
) -> Target:
    return Target(key, domain, label, context, priority, tuple(plans), True, reason)


def build_initial_state() -> PersonalState:
    return PersonalState(
        tick=0,
        profile_key="profile:christophe-demo",
        targets=(
            target(
                "journey:university-payment",
                "payments/readiness",
                "Régler l’obligation de paiement de la démarche universitaire",
                ActorContext.PERSONAL,
                Priority.P1_REQUIRED,
                [
                    p("card", "Payer par carte", 4, 250, 0, 0),
                    p("bank", "Faire un virement bancaire", 18, 0, 0, 0),
                ],
                "beneficiary=profile; payment obligation confirmed",
            ),
            target(
                "journey:visa-form",
                "journeys/forms/readiness",
                "Compléter le formulaire obligatoire du visa",
                ActorContext.PERSONAL,
                Priority.P1_REQUIRED,
                [
                    p("reuse-library", "Réutiliser le document déjà en bibliothèque", 8, 0, 0, 0),
                    p("request-copy", "Demander une nouvelle copie puis compléter", 55, 0, 25, 1),
                ],
                "beneficiary=profile; required form request open",
            ),
            target(
                "action-network:mentor-proposal",
                "social/action_network",
                "Répondre à une proposition de mentorat reçue personnellement",
                ActorContext.PERSONAL,
                Priority.P1_REQUIRED,
                [p("review-respond", "Relire puis répondre", 3, 0, 0, 1)],
                "candidate_profile=profile",
            ),
            target(
                "prepared-start:identity-confirmation",
                "opportunities/prepared_start",
                "Confirmer une preuve d’identité réutilisable",
                ActorContext.PERSONAL,
                Priority.P1_REQUIRED,
                [p("confirm-proof", "Vérifier et confirmer la preuve", 15, 0, 10, 1)],
                "saved opportunity; mandatory trusted-reuse confirmation",
            ),
            target(
                "dossier:study-abroad",
                "objectives/dossier",
                "Faire avancer le Dossier personnel Étudier à l’étranger",
                ActorContext.PERSONAL,
                Priority.P3_PROGRESS,
                [
                    p("link-existing", "Rattacher une démarche existante", 6, 0, 0, 2),
                    p("review-plan", "Relire le plan du Dossier", 10, 0, 0, 1),
                ],
                "Dossier.owner_profile=profile; owning_space=None",
            ),
            target(
                "opportunity:scholarship",
                "opportunities/prepared_start",
                "Préparer la bourse sauvegardée",
                ActorContext.PERSONAL,
                Priority.P3_PROGRESS,
                [
                    p("prepare-now", "Préparer avec les pièces réutilisables", 12, 0, 0, 1),
                    p("manual", "Reconstituer les pièces manuellement", 45, 0, 15, 2),
                ],
                "OpportunitySave(profile=profile)",
            ),
            target(
                "conversation:revisit-travel",
                "conversations",
                "Revoir un point de conversation personnel planifié",
                ActorContext.PERSONAL,
                Priority.P3_PROGRESS,
                [p("revisit", "Revoir le point", 5, 0, 0, 2)],
                "revisit requested for profile",
            ),
            target(
                "discover:concert-tonight",
                "discovery/occurrence",
                "Concert accessible ce soir",
                ActorContext.PERSONAL,
                Priority.P4_INFORMATION,
                [
                    p("walk", "Y aller à pied", 25, 1800, 22, 0),
                    p("taxi", "Y aller en taxi", 8, 1800, 8, 0),
                ],
                "published occurrence; capacity available; public geography",
            ),
            target(
                "discover:workshop-ai",
                "discovery/occurrence",
                "Atelier IA demain",
                ActorContext.PERSONAL,
                Priority.P4_INFORMATION,
                [p("register", "S’inscrire et s’y rendre", 7, 0, 35, 1)],
                "published occurrence; capacity available",
            ),
            target(
                "space-dossier:critical-blocker",
                "objectives/dossier",
                "Résoudre le blocker critique du Dossier de l’Espace",
                ActorContext.SPACE,
                Priority.P0_CRITICAL,
                [p("manage", "Résoudre pour l’Espace", 1, 0, 0, 0)],
                "visible only through Space authority",
            ),
            target(
                "space-action-network:partner",
                "social/action_network",
                "Répondre à une proposition visant l’Espace",
                ActorContext.SPACE,
                Priority.P1_REQUIRED,
                [p("respond", "Répondre au nom de l’Espace", 1, 0, 0, 0)],
                "candidate_space; actor has delegated Space permission",
            ),
            target(
                "space-conversation:resolve",
                "conversations",
                "Résoudre un point opérationnel de l’Espace",
                ActorContext.SPACE,
                Priority.P1_REQUIRED,
                [p("resolve", "Résoudre au nom de l’Espace", 1, 0, 0, 0)],
                "resolve authority comes only from Space permission",
            ),
        ),
    )


def serialise_snapshot(snapshot: Snapshot) -> dict:
    data = asdict(snapshot)
    data["frontier_points"] = [asdict(point) for point in snapshot.frontier_points]
    return data


def run() -> dict:
    state0 = build_initial_state()
    snapshots = [evaluate(state0)]

    state1 = resolve_targets(state0, "journey:university-payment")
    snapshots.append(evaluate(state1))

    state2 = resolve_targets(state1, "journey:visa-form")
    snapshots.append(evaluate(state2))

    state3 = resolve_targets(state2, "action-network:mentor-proposal")
    snapshots.append(evaluate(state3))

    state4 = resolve_targets(state3, "prepared-start:identity-confirmation")
    snapshots.append(evaluate(state4))

    state5 = resolve_targets(
        state4,
        "dossier:study-abroad",
        "opportunity:scholarship",
        "conversation:revisit-travel",
    )
    snapshots.append(evaluate(state5))

    result = {
        "model": "frontiere-opportunite-makolo-personal-lab-v1",
        "profile": state0.profile_key,
        "invariants": {
            "person_context_only": True,
            "weighted_score_used": False,
            "space_authority_may_enter_personal_pool": False,
            "priority_gate_precedes_pareto": True,
        },
        "snapshots": [serialise_snapshot(s) for s in snapshots],
    }

    assert snapshots[0].gate_priority == "P1_REQUIRED"
    assert "space-dossier:critical-blocker" in snapshots[0].excluded_space_targets
    assert "space-action-network:partner" in snapshots[0].excluded_space_targets
    assert "space-conversation:resolve" in snapshots[0].excluded_space_targets
    assert set(snapshots[0].frontier_targets) == {
        "action-network:mentor-proposal",
        "journey:university-payment",
        "journey:visa-form",
    }
    assert "prepared-start:identity-confirmation" in snapshots[0].screened_targets
    assert snapshots[4].gate_priority == "P3_PROGRESS"
    assert snapshots[5].gate_priority == "P4_INFORMATION"
    assert set(snapshots[5].frontier_targets) == {
        "discover:concert-tonight",
        "discover:workshop-ai",
    }
    return result


if __name__ == "__main__":
    result = run()
    rendered = dumps(result, indent=2, ensure_ascii=False)
    print(rendered)
    here = Path(__file__).resolve().parent
    (here / "output.json").write_text(rendered + "\n", encoding="utf-8")
