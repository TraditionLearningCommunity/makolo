from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime, timedelta
from json import dumps
from pathlib import Path
from zoneinfo import ZoneInfo

from engine import (
    Actionability,
    ActorContext,
    DeadlineState,
    Identity,
    Performance,
    Plan,
    Priority,
    Target,
    evaluate_targets,
    serialise_performance,
)

TZ = ZoneInfo("Africa/Lubumbashi")
INF_DEADLINE_MIN = 1_000_000
SAFETY_BUFFER_MIN = 10


@dataclass(frozen=True, slots=True)
class State:
    now: datetime
    profile_key: str = "profile:demo-person"
    payment_done: bool = False
    form_done: bool = False
    capacity_status: str = "held"
    capacity_expires_at: datetime | None = None
    mentor_done: bool = False
    identity_state: str = "confirmation_required"
    recognition_done: bool = False
    personal_owner_proposal_done: bool = False
    bank_letter_state: str = "missing"
    scholarship_state: str = "unknown"
    dossier_done: bool = False
    dossier_hidden_influence: bool = False
    revisit_pending: bool = True
    access_status: str = "valid"
    access_valid_until: datetime | None = None
    departed_for_concert: bool = False
    concert_cancelled: bool = False
    concert_completed: bool = False


@dataclass(frozen=True, slots=True)
class DirectPlan:
    key: str
    label: str
    effort: int
    cash: int
    travel: int
    elapsed: int
    interactions: int
    effect: str
    feasible: bool = True
    infeasible_reason: str = ""


@dataclass(frozen=True, slots=True)
class Spec:
    key: str
    label: str
    identity: Identity
    domain: str
    actor_context: ActorContext
    priority: Priority
    actionability: Actionability
    deadline: datetime | None
    mandatory: bool
    direct_plans: tuple[DirectPlan, ...]
    reason_codes: tuple[str, ...]


def dt(hour: int, minute: int = 0, *, day: int = 10) -> datetime:
    return datetime(2026, 9, day, hour, minute, tzinfo=TZ)


def deadline_state(deadline: datetime | None, now: datetime) -> DeadlineState:
    if deadline is None:
        return DeadlineState.NONE
    if deadline < now:
        return DeadlineState.OVERDUE
    if deadline.astimezone(now.tzinfo).date() == now.date():
        return DeadlineState.DUE_TODAY
    return DeadlineState.FUTURE


def deadline_minutes(deadline: datetime | None, now: datetime) -> int:
    if deadline is None:
        return INF_DEADLINE_MIN
    return max(0, int((deadline - now).total_seconds() // 60))


def identity(domain: str, source: str, action: str, context: str, context_id: str) -> Identity:
    return Identity(domain, source, action, context, context_id)


def _specs(state: State) -> list[Spec]:
    """Project synthetic facts using laws audited from Makolo main.

    Values (amounts, dates, route durations) are scenario data. State transitions,
    ownership boundaries and priority/actionability semantics mirror audited contracts.
    """
    s: list[Spec] = []

    if not state.payment_done:
        s.append(Spec(
            "journey:university-payment",
            "Régler le paiement de la démarche universitaire",
            identity("payment_obligation", "payment:tuition", "pay", "journey", "university"),
            "payments/readiness", ActorContext.PERSONAL, Priority.P1_REQUIRED,
            Actionability.ACTIONABLE, dt(23, 0), True,
            (
                DirectPlan("card", "Payer par carte", 4, 25_000, 0, 4, 1, "payment_done"),
                DirectPlan("bank", "Faire un virement", 10, 0, 0, 18, 2, "payment_done"),
            ), ("payment_required",),
        ))

    if not state.form_done:
        form_identity = identity("questionnaire", "form_request:visa", "complete_form", "journey", "visa")
        form_plans = (
            DirectPlan("prefill", "Réutiliser les données déjà disponibles", 8, 0, 0, 12, 2, "form_done"),
            DirectPlan("manual", "Reconstituer puis saisir le formulaire", 55, 0, 25, 90, 4, "form_done"),
        )
        s.append(Spec(
            "journey:visa-form", "Compléter le formulaire obligatoire du visa",
            form_identity, "questionnaires/readiness", ActorContext.PERSONAL,
            Priority.P1_REQUIRED, Actionability.ACTIONABLE, dt(23, 30), True,
            form_plans, ("form_response_required",),
        ))
        s.append(Spec(
            "journey:visa-form", "Compléter le formulaire obligatoire du visa",
            form_identity, "objectives/dossier", ActorContext.PERSONAL,
            Priority.P1_REQUIRED, Actionability.ACTIONABLE, dt(23, 30), True,
            form_plans, ("dossier.projected_next_action", "form_response_required"),
        ))

    hold_active = (
        state.capacity_status == "committed"
        or (
            state.capacity_status == "held"
            and (state.capacity_expires_at is None or state.capacity_expires_at > state.now)
        )
    )
    if not hold_active and not state.concert_completed:
        s.append(Spec(
            "readiness:concert-capacity", "La capacité du concert n’est plus sécurisée",
            identity("capacity", "journey:concert:capacity", "attention:capacity_not_secured", "journey", "concert"),
            "capacity/readiness", ActorContext.PERSONAL, Priority.P0_CRITICAL,
            Actionability.BLOCKING, None, True, (), ("capacity_not_secured",),
        ))

    if not state.mentor_done:
        s.append(Spec(
            "action-network:mentor", "Répondre à la proposition de mentorat",
            identity("action_network", "proposal:mentor", "respond", "action_proposal", "mentor"),
            "social/action_network", ActorContext.PERSONAL, Priority.P1_REQUIRED,
            Actionability.ACTIONABLE, dt(10, 0, day=11), False,
            (DirectPlan("respond", "Relire puis répondre", 3, 0, 0, 5, 1, "mentor_done"),),
            ("action_proposal.response_required",),
        ))

    if not state.personal_owner_proposal_done:
        s.append(Spec(
            "action-network:personal-owner", "Décider sur une proposition reçue pour mon besoin",
            identity("action_network", "proposal:personal-owner", "respond", "action_proposal", "personal-owner"),
            "social/action_network", ActorContext.PERSONAL, Priority.P1_REQUIRED,
            Actionability.ACTIONABLE, None, False,
            (DirectPlan("decide", "Accepter ou refuser", 7, 0, 0, 8, 2, "personal_owner_proposal_done"),),
            ("action_proposal.response_required",),
        ))

    if state.identity_state == "confirmation_required":
        s.append(Spec(
            "prepared-start:identity", "Confirmer la réutilisation d’une preuve d’identité",
            identity("prepared_start", "requirement:identity", "confirm_reuse", "opportunity_revision", "study-grant"),
            "preparation/prepared_start", ActorContext.PERSONAL, Priority.P1_REQUIRED,
            Actionability.ACTIONABLE, None, True,
            (DirectPlan("confirm", "Vérifier et confirmer", 5, 0, 0, 6, 1, "identity_ready"),),
            ("prepared_start.confirmation_required",),
        ))
    if state.bank_letter_state == "missing":
        s.append(Spec(
            "prepared-start:bank-letter", "Préparer l’attestation bancaire manquante",
            identity("prepared_start", "requirement:bank-letter", "prepare_requirement", "opportunity_revision", "study-grant"),
            "preparation/prepared_start", ActorContext.PERSONAL, Priority.P1_REQUIRED,
            Actionability.ACTIONABLE, None, True,
            (DirectPlan("prepare", "Préparer l’attestation", 25, 0, 0, 35, 3, "bank_letter_ready"),),
            ("prepared_start.no_acceptable_candidate",),
        ))
    if state.scholarship_state == "unknown":
        s.append(Spec(
            "prepared-start:scholarship", "Vérifier une exigence de la bourse sauvegardée",
            identity("prepared_start", "requirement:scholarship", "verify_requirement", "opportunity_revision", "scholarship"),
            "preparation/prepared_start", ActorContext.PERSONAL, Priority.P3_PROGRESS,
            Actionability.ACTIONABLE, None, False,
            (DirectPlan("verify", "Vérifier l’exigence", 12, 0, 0, 15, 2, "scholarship_ready"),),
            ("prepared_start.acceptance_unknown",),
        ))
    elif state.scholarship_state == "review_required":
        s.append(Spec(
            "prepared-start:scholarship-review", "La bourse attend une revue humaine",
            identity("prepared_start", "requirement:scholarship", "review_requirement", "opportunity_revision", "scholarship"),
            "preparation/prepared_start", ActorContext.PERSONAL, Priority.P4_INFORMATION,
            Actionability.WAITING, None, False, (), ("prepared_start.human_review_required",),
        ))

    if not state.recognition_done:
        s.append(Spec(
            "recognition:benefit", "Décider sur le bénéfice proposé",
            identity("recognition", "redemption:benefit", "beneficiary_decision", "recognition_redemption", "benefit"),
            "recognition", ActorContext.PERSONAL, Priority.P1_REQUIRED,
            Actionability.ACTIONABLE, None, False,
            (DirectPlan("decide", "Accepter ou refuser", 6, 0, 0, 7, 1, "recognition_done"),),
            ("recognition.beneficiary_consent_required",),
        ))

    if not state.dossier_done:
        if state.dossier_hidden_influence:
            s.append(Spec(
                "dossier:study-abroad:hidden", "Un élément non visible affecte actuellement l’avancement de ce dossier.",
                identity("dossier", "hidden_influence", "attention:blocked", "dossier", "study-abroad"),
                "objectives/dossier", ActorContext.PERSONAL, Priority.P0_CRITICAL,
                Actionability.BLOCKING, None, False, (), ("dossier.hidden_influence",),
            ))
        else:
            s.append(Spec(
                "dossier:study-abroad", "Faire avancer mon Dossier Étudier à l’étranger",
                identity("dossier", "dossier:study-abroad", "review_plan", "dossier", "study-abroad"),
                "objectives/dossier", ActorContext.PERSONAL, Priority.P3_PROGRESS,
                Actionability.ACTIONABLE, None, False,
                (
                    DirectPlan("review", "Relire le plan", 10, 0, 0, 12, 1, "dossier_done"),
                    DirectPlan("restructure", "Recomposer le plan", 30, 0, 0, 40, 3, "dossier_done"),
                ), ("dossier.progress",),
            ))

    if state.revisit_pending:
        s.append(Spec(
            "conversation:travel-revisit", "Revoir le point de coordination du voyage",
            identity("conversations", "point:travel", "revisit", "conversation", "travel"),
            "conversations", ActorContext.PERSONAL, Priority.P3_PROGRESS,
            Actionability.ACTIONABLE, dt(9, 0, day=11), False,
            (DirectPlan("revisit", "Revoir le point", 5, 0, 0, 7, 1, "revisit_done"),),
            ("conversation.revisit",),
        ))

    access_usable = (
        state.access_status == "valid"
        and (state.access_valid_until is None or state.access_valid_until > state.now)
    )
    if not state.concert_completed:
        if state.concert_cancelled:
            s.append(Spec(
                "readiness:concert-cancelled", "Le concert a été annulé",
                identity("occurrence", "occurrence:concert", "attention:occurrence_cancelled", "journey", "concert"),
                "occurrence/readiness", ActorContext.PERSONAL, Priority.P0_CRITICAL,
                Actionability.TERMINAL, None, True, (), ("occurrence_cancelled",),
            ))
        elif not access_usable:
            s.append(Spec(
                "readiness:concert-access", "Le droit d’accès requis n’est pas disponible",
                identity("access", "journey:concert:access", "attention:access_unavailable", "journey", "concert"),
                "access/readiness", ActorContext.PERSONAL, Priority.P0_CRITICAL,
                Actionability.BLOCKING, None, True, (), ("access_unavailable",),
            ))
            s.append(Spec(
                "m6:concert:access", "Vérifier et restaurer mon accès avant de me déplacer",
                identity("spatiotemporal", "journey:concert:access", "access_action", "journey", "concert"),
                "spatiotemporal", ActorContext.PERSONAL, Priority.P0_CRITICAL,
                Actionability.ACTIONABLE, None, False,
                (DirectPlan("repair", "Restaurer l’accès", 6, 0, 0, 8, 2, "access_restore"),),
                ("access_unavailable",),
            ))
        elif hold_active and not state.departed_for_concert:
            target_arrival = dt(20, 0)
            route_min = 35
            recommended = target_arrival - timedelta(minutes=route_min + SAFETY_BUFFER_MIN)
            if state.now >= recommended:
                s.append(Spec(
                    "m6:concert:leave-now", "C’est le moment recommandé pour partir au concert",
                    identity("spatiotemporal", "occurrence:concert:leave_now", "leave_now", "journey", "concert"),
                    "spatiotemporal", ActorContext.PERSONAL, Priority.P2_TIME_CONSTRAINED,
                    Actionability.ACTIONABLE, target_arrival, False,
                    (DirectPlan("depart", "Partir maintenant", 2, 0, route_min, route_min, 1, "depart_concert"),),
                    ("leave_soon",),
                ))

    discover_specs = [
        ("discover:gallery", "Exposition photo ce soir", 18, 1, 5000, 12, 25, 1, "scheduled", 6),
        ("discover:workshop-ai", "Atelier IA demain", 12, 8, 8000, 35, 45, 2, "scheduled", 4),
        ("discover:workshop-ai", "Atelier IA demain", 12, 10, 2000, 55, 75, 2, "scheduled", 4),
        ("discover:seminar", "Séminaire généraliste demain", 12, 20, 12000, 70, 95, 3, "scheduled", 20),
        ("discover:soldout", "Projection complète demain", 12, 6, 3000, 20, 35, 2, "scheduled", 0),
        ("discover:cancelled", "Rencontre annulée", 12, 3, 0, 10, 20, 1, "cancelled", 10),
    ]
    by_key: dict[str, list[DirectPlan]] = {}
    labels: dict[str, str] = {}
    deadline_hours: dict[str, int] = {}
    capacity: dict[str, int] = {}
    statuses: dict[str, str] = {}
    for key, label, dh, effort, cash, travel, elapsed, interactions, status, available in discover_specs:
        labels[key] = label
        deadline_hours[key] = dh
        capacity[key] = available
        statuses[key] = status
        by_key.setdefault(key, []).append(
            DirectPlan(f"route-{len(by_key.get(key, []))+1}", label, effort, cash, travel, elapsed, interactions, "noop")
        )
    for key, plans in by_key.items():
        if statuses[key] == "cancelled":
            continue
        feasible = capacity[key] > 0
        marked = tuple(
            replace(plan, feasible=feasible, infeasible_reason="capacity_unavailable" if not feasible else "")
            for plan in plans
        )
        s.append(Spec(
            key, labels[key], identity("discovery", key, "consider", "discovery_candidate", key),
            "discovery/occurrence", ActorContext.PERSONAL, Priority.P4_INFORMATION,
            Actionability.ACTIONABLE, state.now + timedelta(hours=deadline_hours[key]), False,
            marked, ("published_occurrence", "capacity_available" if feasible else "capacity_unavailable"),
        ))

    s.extend([
        Spec(
            "dossier:space:hidden", "Résoudre le blocker critique du Dossier de l’Espace",
            identity("dossier", "space:hidden", "attention:blocked", "dossier", "space-dossier"),
            "objectives/dossier", ActorContext.SPACE, Priority.P0_CRITICAL, Actionability.ACTIONABLE,
            state.now, True, (DirectPlan("manage", "Résoudre pour l’Espace", 1, 0, 0, 1, 1, "noop"),),
            ("space_authority_only",),
        ),
        Spec(
            "action-network:proposal:space", "Répondre à une proposition visant l’Espace",
            identity("action_network", "proposal:space", "respond", "action_proposal", "space"),
            "social/action_network", ActorContext.SPACE, Priority.P1_REQUIRED, Actionability.ACTIONABLE,
            state.now, True, (DirectPlan("respond", "Répondre au nom de l’Espace", 1, 0, 0, 1, 1, "noop"),),
            ("space_authority_only",),
        ),
        Spec(
            "conversation:space-resolve", "Résoudre un point opérationnel de l’Espace",
            identity("conversations", "point:space", "resolve", "conversation", "space"),
            "conversations", ActorContext.SPACE, Priority.P1_REQUIRED, Actionability.ACTIONABLE,
            state.now, True, (DirectPlan("resolve", "Résoudre au nom de l’Espace", 1, 0, 0, 1, 1, "noop"),),
            ("space_authority_only",),
        ),
    ])
    return s


def apply_effect(state: State, effect: str, elapsed: int = 0) -> State:
    state = replace(state, now=state.now + timedelta(minutes=elapsed))
    changes = {
        "payment_done": {"payment_done": True},
        "form_done": {"form_done": True},
        "mentor_done": {"mentor_done": True},
        "identity_ready": {"identity_state": "ready"},
        "recognition_done": {"recognition_done": True},
        "personal_owner_proposal_done": {"personal_owner_proposal_done": True},
        "bank_letter_ready": {"bank_letter_state": "ready"},
        "scholarship_ready": {"scholarship_state": "ready"},
        "dossier_done": {"dossier_done": True},
        "revisit_done": {"revisit_pending": False},
        "access_restore": {"access_status": "valid"},
        "depart_concert": {"departed_for_concert": True},
        "noop": {},
    }
    if effect not in changes:
        raise KeyError(effect)
    return replace(state, **changes[effect])


def burden_counts(state: State) -> tuple[int, int, int, int]:
    specs = [spec for spec in _specs(state) if spec.actor_context == ActorContext.PERSONAL]
    best: dict[Identity, Spec] = {}
    for spec in specs:
        current = best.get(spec.identity)
        if current is None or (spec.priority, spec.actionability) < (current.priority, current.actionability):
            best[spec.identity] = spec
    counts = []
    for priority in (Priority.P0_CRITICAL, Priority.P1_REQUIRED, Priority.P2_TIME_CONSTRAINED, Priority.P3_PROGRESS):
        counts.append(sum(
            1 for spec in best.values()
            if spec.priority == priority and spec.actionability in {Actionability.BLOCKING, Actionability.ACTIONABLE}
        ))
    return tuple(counts)  # type: ignore[return-value]


def build_targets(state: State) -> tuple[Target, ...]:
    targets: list[Target] = []
    for spec in _specs(state):
        plans: list[Plan] = []
        for direct in spec.direct_plans:
            next_state = apply_effect(state, direct.effect, direct.elapsed)
            p0, p1, p2, p3 = burden_counts(next_state)
            plans.append(Plan(
                key=direct.key,
                label=direct.label,
                feasible=direct.feasible,
                infeasible_reason=direct.infeasible_reason,
                cost=Performance(
                    deadline_minutes(spec.deadline, state.now),
                    direct.effort,
                    direct.cash,
                    direct.travel,
                    direct.elapsed,
                    direct.interactions,
                    p0, p1, p2, p3,
                ),
            ))
        targets.append(Target(
            key=spec.key,
            label=spec.label,
            identity=spec.identity,
            source_domain=spec.domain,
            actor_context=spec.actor_context,
            priority=spec.priority,
            actionability=spec.actionability,
            deadline_state=deadline_state(spec.deadline, state.now),
            mandatory=spec.mandatory,
            plans=tuple(plans),
            reason_codes=spec.reason_codes,
        ))
    return tuple(targets)


def snapshot(name: str, state: State) -> dict:
    evaluation = evaluate_targets(build_targets(state))
    frontier_targets = sorted({point.target_key for point in evaluation.frontier_points})
    return {
        "name": name,
        "now": state.now.isoformat(),
        "primary_attention": evaluation.primary_attention.key if evaluation.primary_attention else None,
        "primary_attention_priority": evaluation.primary_attention.priority.name if evaluation.primary_attention else None,
        "primary_attention_actionability": evaluation.primary_attention.actionability.name if evaluation.primary_attention else None,
        "primary_action_gate": evaluation.primary_action_gate.key if evaluation.primary_action_gate else None,
        "gate_priority": evaluation.primary_action_gate.priority.name if evaluation.primary_action_gate else None,
        "gate_deadline_state": evaluation.primary_action_gate.deadline_state.name if evaluation.primary_action_gate else None,
        "excluded_space_targets": list(evaluation.excluded_space_targets),
        "eligible_targets": sorted(target.key for target in evaluation.eligible_targets),
        "inaccessible_targets": list(evaluation.inaccessible_targets),
        "deduplicated_identity_count": evaluation.deduplicated_identity_count,
        "screened_targets": list(evaluation.screened_targets),
        "frontier_targets": frontier_targets,
        "frontier_points": [
            {
                "target": point.target_key,
                "plan": point.plan_key,
                "performance": serialise_performance(point.cost),
            }
            for point in evaluation.frontier_points
        ],
    }


def choose_plan(state: State, target_key: str, plan_key: str) -> State:
    evaluation = evaluate_targets(build_targets(state))
    target = next(target for target in evaluation.eligible_targets if target.key == target_key)
    plan = next(plan for plan in target.plans if plan.key == plan_key and plan.feasible)
    spec = next(spec for spec in _specs(state) if spec.key == target_key)
    direct = next(plan0 for plan0 in spec.direct_plans if plan0.key == plan_key)
    return apply_effect(state, direct.effect, direct.elapsed)


def run() -> dict:
    state = State(
        now=dt(16, 0),
        capacity_status="held",
        capacity_expires_at=dt(17, 20),
        access_status="valid",
        access_valid_until=dt(23, 0),
    )
    snapshots: list[dict] = []
    snapshots.append(snapshot("t0_initial_personal_state", state))

    state = choose_plan(state, "journey:university-payment", "card")
    snapshots.append(snapshot("t1_after_payment", state))

    state = choose_plan(state, "journey:visa-form", "prefill")
    snapshots.append(snapshot("t2_after_required_form", state))

    state = replace(state, now=dt(17, 25))
    snapshots.append(snapshot("t3_capacity_hold_expired", state))

    state = replace(state, capacity_status="committed")
    snapshots.append(snapshot("t4_capacity_committed", state))

    state = choose_plan(state, "action-network:mentor", "respond")
    snapshots.append(snapshot("t5_mentor_proposal_answered", state))

    state = choose_plan(state, "prepared-start:identity", "confirm")
    snapshots.append(snapshot("t6_identity_reuse_confirmed", state))

    state = choose_plan(state, "recognition:benefit", "decide")
    snapshots.append(snapshot("t7_recognition_decided", state))

    state = choose_plan(state, "action-network:personal-owner", "decide")
    snapshots.append(snapshot("t8_personal_need_proposal_decided", state))

    state = choose_plan(state, "prepared-start:bank-letter", "prepare")
    snapshots.append(snapshot("t9_bank_letter_prepared", state))

    state = replace(state, dossier_hidden_influence=True)
    snapshots.append(snapshot("t10_hidden_dossier_influence", state))

    state = replace(state, dossier_hidden_influence=False, now=dt(19, 20))
    snapshots.append(snapshot("t11_leave_now", state))

    state = replace(state, access_status="revoked")
    snapshots.append(snapshot("t12_access_revoked", state))

    state = choose_plan(state, "m6:concert:access", "repair")
    snapshots.append(snapshot("t13_access_restored_by_action", state))

    state = choose_plan(state, "m6:concert:leave-now", "depart")
    snapshots.append(snapshot("t14_departed_for_concert", state))

    state = replace(
        state,
        revisit_pending=False,
        dossier_done=True,
        scholarship_state="ready",
    )
    snapshots.append(snapshot("t15_personal_actions_cleared", state))

    state = replace(
        state,
        now=dt(22, 30),
        concert_completed=True,
        access_status="used",
    )
    snapshots.append(snapshot("t16_discovery_frontier", state))

    terminal_state = replace(state, concert_completed=False, concert_cancelled=True, now=dt(19, 0))
    terminal = snapshot("edge_occurrence_cancelled", terminal_state)

    assert snapshots[0]["gate_priority"] == "P1_REQUIRED"
    assert snapshots[0]["gate_deadline_state"] == "DUE_TODAY"
    assert set(snapshots[0]["frontier_targets"]) == {"journey:university-payment", "journey:visa-form"}
    assert snapshots[0]["deduplicated_identity_count"] >= 1
    assert set(snapshots[0]["excluded_space_targets"]) == {
        "action-network:proposal:space", "conversation:space-resolve", "dossier:space:hidden"
    }
    assert snapshots[3]["primary_attention_priority"] == "P0_CRITICAL"
    assert snapshots[3]["primary_action_gate"] is None
    assert snapshots[10]["primary_attention"] == "dossier:study-abroad:hidden"
    assert snapshots[10]["primary_action_gate"] is None
    assert snapshots[11]["gate_priority"] == "P2_TIME_CONSTRAINED"
    assert "m6:concert:leave-now" in snapshots[11]["frontier_targets"]
    assert snapshots[12]["primary_attention_actionability"] == "BLOCKING"
    assert "m6:concert:access" in snapshots[12]["frontier_targets"]
    assert snapshots[16]["gate_priority"] == "P4_INFORMATION"
    assert "discover:soldout" in snapshots[16]["inaccessible_targets"]
    assert "discover:cancelled" not in snapshots[16]["eligible_targets"]
    assert set(snapshots[16]["frontier_targets"]) == {"discover:gallery", "discover:workshop-ai"}
    assert "discover:seminar" in snapshots[16]["screened_targets"]
    assert terminal["primary_attention_actionability"] == "TERMINAL"
    assert terminal["primary_action_gate"] is None
    assert not terminal["frontier_targets"]
    assert all(not set(s["frontier_targets"]).intersection(s["screened_targets"]) for s in snapshots)

    return {
        "model": "frontiere-opportunite-makolo-personal-lab-v2",
        "base_main_sha": "a840455af8cd3cfc185404b4dc8c28a53bbb9eb6",
        "scenario_data": "synthetic but constrained by audited Makolo contracts",
        "invariants": {
            "represented_space_is_none": True,
            "space_authority_excluded_before_r2": True,
            "readiness_precedes_frontier": True,
            "r2_priority_and_deadline_state_gate_precede_pareto": True,
            "exact_identity_deduplication": True,
            "capacity_held_expiry_semantics": True,
            "access_status_and_validity_applied": True,
            "m6_leave_now_and_access_override_applied": True,
            "prepared_start_states_preserved": True,
            "no_weighted_score": True,
            "continuation_from_current_state": True,
            "safe_screening_has_no_false_frontier_rejection": True,
        },
        "snapshots": snapshots,
        "edge_cases": [terminal],
    }


if __name__ == "__main__":
    result = run()
    rendered = dumps(result, indent=2, ensure_ascii=False)
    print(rendered)
    output = Path(__file__).resolve().parent / "output.json"
    output.write_text(rendered + "\n", encoding="utf-8")
