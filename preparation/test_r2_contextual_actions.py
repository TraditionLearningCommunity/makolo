from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone as datetime_timezone
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import SimpleTestCase, TestCase

from activities.models import Activity
from journeys.models import Journey, WorkflowKind
from objectives.readiness import DossierNextAction, DossierReadinessItem, DossierReadinessResult
from readiness import resolve_journey_readiness
from readiness.types import (
    NextAction,
    ReadinessCheck,
    ReadinessCheckState,
    ReadinessResult,
    ReadinessStatus,
)
from requirements.contracts import RequirementAssessmentState
from spatiotemporal.types import ActionAdvice

from .contextual_actions import (
    ContextualAction,
    ContextualActionIdentity,
    ContextualActionPriority,
    ContextualActionability,
    ContextualDeadlineState,
    actions_from_action_advices,
    actions_from_dossier,
    actions_from_prepared_start,
    actions_from_readiness,
    classify_contextual_deadline,
    contextual_action_result_signature,
    contextual_action_signature,
    resolve_contextual_actions,
)
from .prepared_start import (
    PreparedRequirementResult,
    PreparedRequirementState,
    PreparedStartContext,
    PreparedStartResult,
    PreparedStartSummary,
)


User = get_user_model()
UTC = datetime_timezone.utc


def _readiness_result(*checks, observed_at, next_action=None, status=ReadinessStatus.ACTION_REQUIRED):
    return ReadinessResult(
        status=status,
        checks=tuple(checks),
        next_action=next_action,
        observed_at=observed_at,
    )


def _check(
    key,
    source,
    state,
    reason_code,
    summary,
    *,
    action=None,
    blocking=False,
):
    return ReadinessCheck(
        key=key,
        source=source,
        state=state,
        blocking=blocking,
        reason_code=reason_code,
        summary=summary,
        next_action=action,
    )


def _action(now, *, source_key="source:1", action_key="act", label="Agir", **overrides):
    values = {
        "identity": ContextualActionIdentity(
            source_domain="test",
            source_key=source_key,
            action_key=action_key,
            context_type="journey",
            context_id="journey-1",
        ),
        "kind": "test.action",
        "priority": ContextualActionPriority.P3_PROGRESS,
        "actionability": ContextualActionability.ACTIONABLE,
        "reason_codes": ("test.reason",),
        "label": label,
        "summary": label,
        "observed_at": now,
    }
    values.update(overrides)
    return ContextualAction(**values)


class R2ContextContractTests(SimpleTestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 3, 12, 0, tzinfo=UTC)

    def test_contextual_action_is_immutable_and_explicit(self):
        action = _action(self.now, url="/safe/action")

        self.assertEqual(action.identity.source_domain, "test")
        self.assertEqual(action.priority, ContextualActionPriority.P3_PROGRESS)
        self.assertEqual(action.actionability, ContextualActionability.ACTIONABLE)
        self.assertEqual(action.observed_at, self.now)
        self.assertEqual(action.url, "/safe/action")
        with self.assertRaises(FrozenInstanceError):
            action.label = "Mutation interdite"

    def test_deadline_states_use_only_exact_canonical_datetime(self):
        self.assertEqual(
            classify_contextual_deadline(self.now - timedelta(minutes=1), observed_at=self.now),
            ContextualDeadlineState.OVERDUE,
        )
        self.assertEqual(
            classify_contextual_deadline(self.now + timedelta(hours=1), observed_at=self.now),
            ContextualDeadlineState.DUE_TODAY,
        )
        self.assertEqual(
            classify_contextual_deadline(self.now + timedelta(days=1), observed_at=self.now),
            ContextualDeadlineState.FUTURE,
        )
        self.assertEqual(
            classify_contextual_deadline(None, observed_at=self.now),
            ContextualDeadlineState.NONE,
        )

    def test_tie_break_is_stable_and_not_input_order_dependent(self):
        later_id = _action(self.now, source_key="source:z")
        earlier_id = _action(self.now, source_key="source:a")

        first = resolve_contextual_actions((later_id, earlier_id), observed_at=self.now)
        second = resolve_contextual_actions((earlier_id, later_id), observed_at=self.now)

        self.assertEqual([item.identity.source_key for item in first.actions], ["source:a", "source:z"])
        self.assertEqual(first.actions, second.actions)
        self.assertEqual(
            contextual_action_result_signature(first),
            contextual_action_result_signature(second),
        )

    def test_signature_ignores_wording_punctuation_and_observation_time(self):
        original = _action(self.now, label="Payer")
        wording = replace(
            original,
            label="Effectuer le paiement !",
            summary="Effectuer le paiement, maintenant.",
            observed_at=self.now + timedelta(minutes=10),
        )

        self.assertEqual(contextual_action_signature(original), contextual_action_signature(wording))

    def test_signature_changes_on_material_semantics(self):
        base = _action(self.now, url="/pay/1")
        variants = (
            replace(
                base,
                identity=replace(base.identity, source_key="source:2"),
            ),
            replace(base, actionability=ContextualActionability.WAITING),
            replace(base, priority=ContextualActionPriority.P1_REQUIRED),
            replace(base, confirmation_required=True),
            replace(base, url="/pay/2"),
            replace(
                base,
                deadline=self.now + timedelta(days=2),
                deadline_state=ContextualDeadlineState.FUTURE,
            ),
        )

        base_signature = contextual_action_signature(base)
        for variant in variants:
            with self.subTest(variant=variant):
                self.assertNotEqual(base_signature, contextual_action_signature(variant))

    def test_deadline_state_change_is_material_even_when_observed_at_is_not(self):
        deadline = self.now + timedelta(hours=1)
        future = _action(
            self.now,
            deadline=deadline,
            deadline_state=ContextualDeadlineState.DUE_TODAY,
        )
        after = replace(
            future,
            observed_at=deadline + timedelta(minutes=1),
            deadline_state=ContextualDeadlineState.OVERDUE,
        )

        self.assertNotEqual(contextual_action_signature(future), contextual_action_signature(after))


class R2ReadinessCompatibilityTests(SimpleTestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 3, 12, 0, tzinfo=UTC)

    def test_single_m1_next_action_is_adapted_without_changing_history_contract(self):
        next_action = NextAction(key="continue_journey", label="Continuer", url="/journey/1", source="journey")
        check = _check(
            "journey.status",
            "journey",
            ReadinessCheckState.ACTION_REQUIRED,
            "journey_draft",
            "La démarche doit être complétée.",
            action=next_action,
        )
        result = _readiness_result(check, observed_at=self.now, next_action=next_action)

        actions = actions_from_readiness(result, context_type="journey", context_id="j1")

        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].identity.action_key, "continue_journey")
        self.assertEqual(actions[0].reason_codes, ("journey_draft",))
        self.assertIs(result.next_action, next_action)
        self.assertEqual(result.next_action.label, "Continuer")
        self.assertEqual(result.next_action.source, "journey")

    def test_r2_considers_all_checks_instead_of_historical_contributor_order(self):
        draft_action = NextAction("continue_journey", "Continuer", source="journey")
        pay_action = NextAction("pay", "Payer", source="payment_obligation")
        draft = _check(
            "journey.status",
            "journey",
            ReadinessCheckState.ACTION_REQUIRED,
            "journey_draft",
            "Continuer la démarche.",
            action=draft_action,
        )
        payment = _check(
            "payment_obligation.payment-1",
            "payment_obligation",
            ReadinessCheckState.ACTION_REQUIRED,
            "payment_required",
            "Frais obligatoires.",
            action=pay_action,
        )
        result = _readiness_result(draft, payment, observed_at=self.now, next_action=draft_action)

        ranked = resolve_contextual_actions(
            actions_from_readiness(result, context_type="journey", context_id="j1"),
            observed_at=self.now,
        )

        self.assertIs(result.next_action, draft_action)
        self.assertEqual(ranked.primary_action.identity.source_key, "payment_obligation.payment-1")
        self.assertEqual(ranked.primary_action.priority, ContextualActionPriority.P1_REQUIRED)

    def test_canonical_deadline_breaks_tie_without_inventing_urgency_window(self):
        today = NextAction("pay", "Payer A", source="payment_obligation")
        later = NextAction("pay", "Payer B", source="payment_obligation")
        today_check = _check(
            "payment_obligation.a",
            "payment_obligation",
            ReadinessCheckState.ACTION_REQUIRED,
            "payment_required",
            "Paiement A",
            action=today,
        )
        later_check = _check(
            "payment_obligation.b",
            "payment_obligation",
            ReadinessCheckState.ACTION_REQUIRED,
            "payment_required",
            "Paiement B",
            action=later,
        )
        result = _readiness_result(today_check, later_check, observed_at=self.now, next_action=later)
        deadlines = {
            "payment_obligation.a": self.now + timedelta(hours=2),
            "payment_obligation.b": self.now + timedelta(days=3),
        }

        ranked = resolve_contextual_actions(
            actions_from_readiness(
                result,
                context_type="journey",
                context_id="j1",
                canonical_deadlines=deadlines,
            ),
            observed_at=self.now,
        )

        self.assertEqual(ranked.primary_action.identity.source_key, "payment_obligation.a")
        self.assertEqual(ranked.primary_action.deadline_state, ContextualDeadlineState.DUE_TODAY)
        self.assertEqual(ranked.actions[1].deadline_state, ContextualDeadlineState.FUTURE)

    def test_cancelled_occurrence_dominates_attention_and_suppresses_payment_cta(self):
        pay_action = NextAction("pay", "Payer", source="payment_obligation")
        cancellation = _check(
            "occurrence",
            "occurrence",
            ReadinessCheckState.BLOCKING,
            "occurrence_cancelled",
            "L’occurrence a été annulée.",
            blocking=True,
        )
        payment = _check(
            "payment_obligation.p1",
            "payment_obligation",
            ReadinessCheckState.ACTION_REQUIRED,
            "payment_required",
            "Paiement requis.",
            action=pay_action,
        )
        historical = _readiness_result(
            cancellation,
            payment,
            observed_at=self.now,
            next_action=pay_action,
            status=ReadinessStatus.BLOCKED,
        )

        ranked = resolve_contextual_actions(
            actions_from_readiness(historical, context_type="journey", context_id="j1"),
            observed_at=self.now,
        )

        self.assertEqual(ranked.primary_attention.reason_codes, ("occurrence_cancelled",))
        self.assertEqual(ranked.primary_attention.actionability, ContextualActionability.TERMINAL)
        self.assertIsNone(ranked.primary_action)
        self.assertIs(historical.next_action, pay_action)

    def test_same_label_different_payment_id_is_never_deduplicated(self):
        checks = tuple(
            _check(
                f"payment_obligation.{index}",
                "payment_obligation",
                ReadinessCheckState.ACTION_REQUIRED,
                "payment_required",
                "Même libellé",
                action=NextAction("pay", "Payer", source="payment_obligation"),
            )
            for index in (1, 2)
        )
        result = _readiness_result(*checks, observed_at=self.now, next_action=checks[0].next_action)

        ranked = resolve_contextual_actions(
            actions_from_readiness(result, context_type="journey", context_id="j1"),
            observed_at=self.now,
        )

        self.assertEqual(len(ranked.actions), 2)
        self.assertNotEqual(ranked.actions[0].identity.source_key, ranked.actions[1].identity.source_key)

    def test_assignment_like_waiting_never_becomes_action_without_owner_projection(self):
        waiting = _check(
            "journey.step.step-1",
            "journey_step",
            ReadinessCheckState.WAITING,
            "operator_step_pending",
            "Un opérateur doit agir.",
        )
        result = _readiness_result(
            waiting,
            observed_at=self.now,
            next_action=None,
            status=ReadinessStatus.WAITING,
        )

        ranked = resolve_contextual_actions(
            actions_from_readiness(result, context_type="journey", context_id="j1"),
            observed_at=self.now,
        )

        self.assertEqual(ranked.primary_attention.actionability, ContextualActionability.WAITING)
        self.assertIsNone(ranked.primary_action)


class R2PreparedStartAdapterTests(SimpleTestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 3, 12, 0, tzinfo=UTC)
        self.context = PreparedStartContext(
            actor_id="actor",
            viewer_id="actor",
            controller_id="actor",
            subject_type="profile",
            subject_id="actor",
            beneficiary_type="profile",
            beneficiary_id="actor",
            initiator_id="actor",
        )

    def _item(self, requirement_id, state, *, mandatory=True):
        reason = {
            PreparedRequirementState.READY: "prepared_start.trusted_reuse_ready",
            PreparedRequirementState.REVIEW_REQUIRED: "prepared_start.human_review_required",
            PreparedRequirementState.CONFIRMATION_REQUIRED: "prepared_start.confirmation_required",
            PreparedRequirementState.UNKNOWN: "prepared_start.acceptance_unknown",
            PreparedRequirementState.MISSING: "prepared_start.no_acceptable_candidate",
        }[state]
        next_action = {
            PreparedRequirementState.CONFIRMATION_REQUIRED: NextAction(
                "confirm_reuse",
                "Confirmer la réutilisation",
                source="prepared_start",
            ),
            PreparedRequirementState.UNKNOWN: NextAction(
                "verify_requirement",
                "Vérifier l’exigence",
                source="prepared_start",
            ),
            PreparedRequirementState.MISSING: NextAction(
                "prepare_requirement",
                "Préparer l’élément",
                source="prepared_start",
            ),
        }.get(state)
        check_state = {
            PreparedRequirementState.READY: ReadinessCheckState.SATISFIED,
            PreparedRequirementState.REVIEW_REQUIRED: ReadinessCheckState.WAITING,
        }.get(state, ReadinessCheckState.ACTION_REQUIRED)
        check = _check(
            f"prepared_requirement:{requirement_id}",
            "prepared_start",
            check_state,
            reason,
            f"Requirement {requirement_id}",
            action=next_action,
            blocking=mandatory and state != PreparedRequirementState.READY,
        )
        return PreparedRequirementResult(
            requirement_id=requirement_id,
            kind="document",
            title=f"Requirement {requirement_id}",
            mandatory=mandatory,
            position=1,
            assessment_state=RequirementAssessmentState.UNASSESSED,
            preparation_state=state,
            readiness_check=check,
            reason_codes=(reason,),
            reuse_options=(),
        )

    def _result(self, *items):
        readiness = _readiness_result(
            observed_at=self.now,
            next_action=None,
            status=ReadinessStatus.ACTION_REQUIRED,
        )
        return PreparedStartResult(
            context=self.context,
            opportunity_id="opportunity-1",
            revision_id="revision-7",
            revision_version=7,
            observed_at=self.now,
            readiness=readiness,
            requirements=tuple(items),
            summary=PreparedStartSummary(
                total_requirements=len(items),
                mandatory_requirements=sum(1 for item in items if item.mandatory),
                ready_requirements=sum(1 for item in items if item.preparation_state == PreparedRequirementState.READY),
                review_required_requirements=sum(1 for item in items if item.preparation_state == PreparedRequirementState.REVIEW_REQUIRED),
                confirmation_required_requirements=sum(1 for item in items if item.preparation_state == PreparedRequirementState.CONFIRMATION_REQUIRED),
                unknown_requirements=sum(1 for item in items if item.preparation_state == PreparedRequirementState.UNKNOWN),
                missing_requirements=sum(1 for item in items if item.preparation_state == PreparedRequirementState.MISSING),
            ),
        )

    def test_ready_does_not_create_false_action(self):
        result = self._result(self._item("ready", PreparedRequirementState.READY))
        self.assertEqual(actions_from_prepared_start(result), ())

    def test_confirmation_missing_unknown_and_review_keep_exact_semantics(self):
        result = self._result(
            self._item("confirm", PreparedRequirementState.CONFIRMATION_REQUIRED),
            self._item("missing", PreparedRequirementState.MISSING),
            self._item("unknown", PreparedRequirementState.UNKNOWN),
            self._item("review", PreparedRequirementState.REVIEW_REQUIRED),
        )
        by_key = {action.identity.source_key: action for action in actions_from_prepared_start(result)}

        self.assertTrue(by_key["requirement:confirm"].confirmation_required)
        self.assertEqual(by_key["requirement:missing"].identity.action_key, "prepare_requirement")
        self.assertEqual(by_key["requirement:unknown"].reason_codes, ("prepared_start.acceptance_unknown",))
        self.assertEqual(by_key["requirement:unknown"].priority, ContextualActionPriority.P3_PROGRESS)
        self.assertEqual(by_key["requirement:review"].actionability, ContextualActionability.WAITING)

    def test_mandatory_gap_outranks_optional_gap(self):
        result = self._result(
            self._item("a-optional", PreparedRequirementState.MISSING, mandatory=False),
            self._item("z-mandatory", PreparedRequirementState.MISSING, mandatory=True),
        )

        ranked = resolve_contextual_actions(actions_from_prepared_start(result), observed_at=self.now)

        self.assertEqual(ranked.primary_action.identity.source_key, "requirement:z-mandatory")
        self.assertEqual(ranked.primary_action.priority, ContextualActionPriority.P1_REQUIRED)

    def test_confirmation_action_outranks_unknown_without_turning_unknown_into_missing(self):
        result = self._result(
            self._item("unknown", PreparedRequirementState.UNKNOWN, mandatory=True),
            self._item("confirm", PreparedRequirementState.CONFIRMATION_REQUIRED, mandatory=True),
        )

        ranked = resolve_contextual_actions(actions_from_prepared_start(result), observed_at=self.now)

        self.assertEqual(ranked.primary_action.identity.action_key, "confirm_reuse")
        unknown = next(action for action in ranked.actions if action.identity.source_key == "requirement:unknown")
        self.assertEqual(unknown.kind, "prepared_requirement.unknown")
        self.assertNotIn("prepared_start.no_acceptable_candidate", unknown.reason_codes)

    def test_exact_requirement_and_revision_are_part_of_identity(self):
        result = self._result(self._item("req-42", PreparedRequirementState.MISSING))
        action = actions_from_prepared_start(result)[0]

        self.assertEqual(action.identity.source_key, "requirement:req-42")
        self.assertEqual(action.identity.context_type, "opportunity_revision")
        self.assertEqual(action.identity.context_id, "revision-7")


class R2M6AdapterTests(SimpleTestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 3, 12, 0, tzinfo=UTC)

    def _advice(self, kind, *, reason_code=None, source_key=None, action_url=""):
        return ActionAdvice(
            kind=kind,
            priority={
                "cancelled": 100,
                "access_action": 90,
                "leave_now": 80,
                "warning": 60,
                "information": 20,
            }.get(kind, 1),
            reason_code=reason_code or kind,
            summary=f"Advice {kind}",
            observed_at=self.now,
            action_url=action_url,
            source_key=source_key or f"source:{kind}",
        )

    def test_m6_conversion_is_declarative(self):
        expected = {
            "cancelled": (ContextualActionPriority.P0_CRITICAL, ContextualActionability.TERMINAL),
            "access_action": (ContextualActionPriority.P0_CRITICAL, ContextualActionability.ACTIONABLE),
            "leave_now": (ContextualActionPriority.P2_TIME_CONSTRAINED, ContextualActionability.ACTIONABLE),
            "warning": (ContextualActionPriority.P4_INFORMATION, ContextualActionability.ADVICE),
            "information": (ContextualActionPriority.P4_INFORMATION, ContextualActionability.INFORMATION),
        }
        actions = actions_from_action_advices(
            (self._advice(kind) for kind in expected),
            context_type="journey",
            context_id="j1",
        )
        by_kind = {action.identity.action_key: action for action in actions}

        for kind, policy in expected.items():
            with self.subTest(kind=kind):
                self.assertEqual((by_kind[kind].priority, by_kind[kind].actionability), policy)
                self.assertEqual(by_kind[kind].identity.source_domain, "spatiotemporal")

    def test_access_blocker_dominates_leave_now_and_access_resolution_can_remain_primary_action(self):
        access_check = _check(
            "access",
            "access",
            ReadinessCheckState.BLOCKING,
            "access_unavailable",
            "Le droit d’accès n’est pas disponible.",
            blocking=True,
        )
        readiness = _readiness_result(
            access_check,
            observed_at=self.now,
            next_action=None,
            status=ReadinessStatus.BLOCKED,
        )
        leave_now = self._advice("leave_now", reason_code="leave_soon", action_url="/itinerary")
        access_action = self._advice(
            "access_action",
            reason_code="access_unavailable",
            source_key="journey:j1:access",
            action_url="/journey/j1",
        )

        ranked = resolve_contextual_actions(
            (
                *actions_from_readiness(readiness, context_type="journey", context_id="j1"),
                *actions_from_action_advices(
                    (leave_now, access_action),
                    context_type="journey",
                    context_id="j1",
                ),
            ),
            observed_at=self.now,
        )

        self.assertEqual(ranked.primary_attention.reason_codes, ("access_unavailable",))
        self.assertEqual(ranked.primary_attention.actionability, ContextualActionability.BLOCKING)
        self.assertEqual(ranked.primary_action.identity.action_key, "access_action")
        self.assertNotEqual(ranked.primary_action.identity.action_key, "leave_now")

    def test_cancelled_m6_advice_never_yields_departure_action(self):
        ranked = resolve_contextual_actions(
            actions_from_action_advices(
                (
                    self._advice("leave_now", action_url="/itinerary"),
                    self._advice("cancelled", reason_code="occurrence_cancelled"),
                ),
                context_type="journey",
                context_id="j1",
            ),
            observed_at=self.now,
        )

        self.assertEqual(ranked.primary_attention.identity.action_key, "cancelled")
        self.assertIsNone(ranked.primary_action)


class R2DossierAdapterTests(SimpleTestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 3, 12, 0, tzinfo=UTC)
        self.dossier = SimpleNamespace(pk="dossier-1", get_lifecycle_display=lambda: "Actif")

    def _dossier_result(self, *, item=None, hidden_signal=None, status=ReadinessStatus.ACTION_REQUIRED):
        items = (item,) if item is not None else ()
        primary = item.next_action if item is not None else None
        return DossierReadinessResult(
            dossier=self.dossier,
            status=status,
            is_partial=bool(hidden_signal),
            visible_items=items,
            visible_dependencies=(),
            hidden_signal=hidden_signal,
            primary_next_action=primary,
        )

    def test_visible_dossier_action_with_canonical_identity_deduplicates_with_readiness(self):
        next_action = NextAction("pay", "Payer", url="/pay/1", source="payment_obligation")
        check = _check(
            "payment_obligation.p1",
            "payment_obligation",
            ReadinessCheckState.ACTION_REQUIRED,
            "payment_required",
            "Paiement requis.",
            action=next_action,
        )
        readiness = _readiness_result(check, observed_at=self.now, next_action=next_action)
        dossier_action = DossierNextAction(
            label="Payer",
            url="/pay/1",
            journey_id="j1",
            key="pay",
            source="payment_obligation",
            source_key="payment_obligation.p1",
            reason_code="payment_required",
        )
        item = DossierReadinessItem(
            journey_id="j1",
            label="Démarche visible",
            status=ReadinessStatus.ACTION_REQUIRED,
            next_action=dossier_action,
        )

        direct = actions_from_readiness(readiness, context_type="journey", context_id="j1")
        from_dossier = actions_from_dossier(self._dossier_result(item=item), observed_at=self.now)
        ranked = resolve_contextual_actions((*direct, *from_dossier), observed_at=self.now)

        self.assertEqual(len(ranked.actions), 1)
        self.assertEqual(ranked.actions[0].identity.source_key, "payment_obligation.p1")
        self.assertEqual(ranked.actions[0].reason_codes, ("payment_required",))

    def test_legacy_dossier_projection_is_not_deduplicated_by_label_or_url(self):
        next_action = NextAction("pay", "Payer", url="/same", source="payment_obligation")
        check = _check(
            "payment_obligation.p1",
            "payment_obligation",
            ReadinessCheckState.ACTION_REQUIRED,
            "payment_required",
            "Paiement requis.",
            action=next_action,
        )
        readiness = _readiness_result(check, observed_at=self.now, next_action=next_action)
        legacy_action = DossierNextAction(label="Payer", url="/same", journey_id="j1")
        item = DossierReadinessItem(
            journey_id="j1",
            label="Démarche visible",
            status=ReadinessStatus.ACTION_REQUIRED,
            next_action=legacy_action,
        )

        ranked = resolve_contextual_actions(
            (
                *actions_from_readiness(readiness, context_type="journey", context_id="j1"),
                *actions_from_dossier(self._dossier_result(item=item), observed_at=self.now),
            ),
            observed_at=self.now,
        )

        self.assertEqual(len(ranked.actions), 2)
        self.assertNotEqual(ranked.actions[0].identity, ranked.actions[1].identity)

    def test_hidden_dependency_remains_one_opaque_attention_item(self):
        hidden_signal = "Un élément non visible affecte actuellement l’avancement de ce dossier."
        result = self._dossier_result(
            hidden_signal=hidden_signal,
            status=ReadinessStatus.BLOCKED,
        )

        actions = actions_from_dossier(result, observed_at=self.now)

        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].summary, hidden_signal)
        self.assertEqual(actions[0].identity.source_domain, "dossier")
        self.assertEqual(actions[0].identity.context_id, "dossier-1")
        self.assertEqual(actions[0].reason_codes, ("dossier.hidden_influence",))
        self.assertIsNone(actions[0].url)

    def test_historical_dossier_next_action_constructor_remains_compatible(self):
        action = DossierNextAction(label="Continuer", url=None, journey_id="j1")
        self.assertEqual(action.key, "")
        self.assertEqual(action.source_key, "")


class R2PermissionBoundaryTests(TestCase):
    def test_m1_permission_gate_fails_before_r2_can_compose_another_beneficiary(self):
        beneficiary = User.objects.create_user(username="r2-beneficiary", password="StrongPass2026!")
        outsider = User.objects.create_user(username="r2-outsider", password="StrongPass2026!")
        activity = Activity.objects.create(
            owner_profile=beneficiary,
            created_by=beneficiary,
            title="Démarche privée",
        )
        journey = Journey.objects.create(
            initiated_by=beneficiary,
            beneficiary=beneficiary,
            activity=activity,
            workflow=WorkflowKind.SERVICE,
        )

        with self.assertRaises(PermissionDenied):
            resolve_journey_readiness(journey, viewer=outsider)

    def test_authorized_participant_projection_can_be_composed_without_extra_queries(self):
        beneficiary = User.objects.create_user(username="r2-owner", password="StrongPass2026!")
        activity = Activity.objects.create(
            owner_profile=beneficiary,
            created_by=beneficiary,
            title="Démarche personnelle",
        )
        journey = Journey.objects.create(
            initiated_by=beneficiary,
            beneficiary=beneficiary,
            activity=activity,
            workflow=WorkflowKind.SERVICE,
        )
        projection = resolve_journey_readiness(journey, viewer=beneficiary)

        with self.assertNumQueries(0):
            actions = actions_from_readiness(projection, context_type="journey", context_id=str(journey.pk))
            resolve_contextual_actions(actions, observed_at=projection.observed_at)


class R2NoSideEffectsTests(TestCase):
    def test_normalization_has_no_business_side_effects(self):
        from access.models import Access
        from automation.models import AutomationRun
        from capacity.models import CapacityReservation
        from core.models import DomainEventOutbox
        from journeys.collaboration_models import JourneyArtifact, JourneyStep
        from notifications.models import Notification
        from objectives.models import Dossier, DossierAssignment
        from payments.models import Payment, PaymentObligation
        from personal_assets.models import PersonalAssetUse
        from services.models import ServiceRequirementAssessment, ServiceRequirementEvidence
        from trust.models import Proof

        models = (
            Journey,
            JourneyStep,
            Payment,
            PaymentObligation,
            Access,
            CapacityReservation,
            ServiceRequirementAssessment,
            ServiceRequirementEvidence,
            PersonalAssetUse,
            JourneyArtifact,
            Proof,
            Dossier,
            DossierAssignment,
            Notification,
            AutomationRun,
            DomainEventOutbox,
        )
        before = {model: model.objects.count() for model in models}
        now = datetime(2026, 9, 3, 12, 0, tzinfo=UTC)
        checks = tuple(
            _check(
                f"payment_obligation.{index}",
                "payment_obligation",
                ReadinessCheckState.ACTION_REQUIRED,
                "payment_required",
                f"Paiement {index}",
                action=NextAction("pay", "Payer", source="payment_obligation"),
            )
            for index in range(30)
        )
        projection = _readiness_result(
            *checks,
            observed_at=now,
            next_action=checks[0].next_action,
        )

        with self.assertNumQueries(0):
            actions = actions_from_readiness(projection, context_type="journey", context_id="j1")
            ranked = resolve_contextual_actions(actions, observed_at=now)
            contextual_action_result_signature(ranked)

        after = {model: model.objects.count() for model in models}
        self.assertEqual(before, after)
        self.assertEqual(len(ranked.actions), 30)
