from dataclasses import replace
from datetime import datetime, timedelta, timezone as dt_timezone

from django.test import SimpleTestCase

from preparation.contextual_actions import (
    ContextualAction,
    ContextualActionIdentity,
    ContextualActionPriority,
    ContextualActionResult,
    ContextualActionability,
    ContextualDeadlineState,
    contextual_action_result_signature,
)
from preparation.proactive_preparation import (
    NOTIFICATION_SIGNATURE_VERSION,
    PreparationTransitionKind,
    classify_preparation_transition,
    deadline_only_transition,
    proactive_notification_signature,
)


NOW = datetime(2026, 9, 4, 1, 0, tzinfo=dt_timezone.utc)


def action(
    action_key="prepare_requirement",
    *,
    source_key="requirement:1",
    context_id="revision-1",
    priority=ContextualActionPriority.P1_REQUIRED,
    actionability=ContextualActionability.ACTIONABLE,
    label="Préparer",
    summary="Préparer cet élément.",
    observed_at=NOW,
    reason_codes=("prepared_start.no_acceptable_candidate",),
    deadline=None,
    deadline_state=ContextualDeadlineState.NONE,
    mandatory=True,
    confirmation_required=False,
):
    return ContextualAction(
        identity=ContextualActionIdentity(
            source_domain="prepared_start",
            source_key=source_key,
            action_key=action_key,
            context_type="opportunity_revision",
            context_id=context_id,
        ),
        kind="prepared_requirement.missing",
        priority=priority,
        actionability=actionability,
        reason_codes=reason_codes,
        label=label,
        summary=summary,
        observed_at=observed_at,
        deadline=deadline,
        deadline_state=deadline_state,
        mandatory=mandatory,
        confirmation_required=confirmation_required,
    )


def result(primary, *secondary, observed_at=NOW):
    actions = (primary, *secondary) if primary is not None else tuple(secondary)
    return ContextualActionResult(
        actions=actions,
        primary_attention=primary,
        primary_action=(
            primary
            if primary is not None and primary.actionability == ContextualActionability.ACTIONABLE
            else None
        ),
        observed_at=observed_at,
    )


class R3NotificationSignatureTests(SimpleTestCase):
    def test_signature_has_explicit_version(self):
        self.assertTrue(
            proactive_notification_signature(result(action())).startswith(
                f"{NOTIFICATION_SIGNATURE_VERSION}:"
            )
        )

    def test_label_summary_and_observed_at_do_not_change_notification_signature(self):
        base = result(action())
        changed = result(
            replace(
                action(),
                label="Effectuer la préparation",
                summary="Reformulation sans changement métier !",
                observed_at=NOW + timedelta(hours=1),
            ),
            observed_at=NOW + timedelta(hours=1),
        )
        self.assertEqual(
            proactive_notification_signature(base),
            proactive_notification_signature(changed),
        )
        self.assertFalse(classify_preparation_transition(base, changed).material)

    def test_reason_url_and_secondary_action_changes_do_not_notify(self):
        primary = action()
        old_secondary = action(
            "information",
            source_key="secondary:1",
            priority=ContextualActionPriority.P4_INFORMATION,
            actionability=ContextualActionability.INFORMATION,
            mandatory=False,
        )
        new_secondary = replace(
            old_secondary,
            reason_codes=("technical.new_reason",),
            summary="Nouveau résumé",
        )
        previous = result(primary, old_secondary)
        current = result(primary, new_secondary)
        self.assertNotEqual(
            contextual_action_result_signature(previous),
            contextual_action_result_signature(current),
        )
        transition = classify_preparation_transition(previous, current)
        self.assertEqual(transition.kind, PreparationTransitionKind.NON_MATERIAL)
        self.assertFalse(transition.material)

    def test_primary_action_identity_change_is_material_and_reversible(self):
        a = result(action("prepare_requirement"))
        b = result(action("confirm_reuse", confirmation_required=True))
        self.assertTrue(classify_preparation_transition(a, b).material)
        self.assertTrue(classify_preparation_transition(b, a).material)

    def test_actionability_change_is_material(self):
        previous = result(action(actionability=ContextualActionability.ACTIONABLE))
        waiting_action = action(actionability=ContextualActionability.WAITING)
        current = ContextualActionResult(
            actions=(waiting_action,),
            primary_attention=waiting_action,
            primary_action=None,
            observed_at=NOW,
        )
        transition = classify_preparation_transition(previous, current)
        self.assertTrue(transition.material)
        self.assertIn("primary_attention_actionability_changed", transition.reasons)

    def test_terminal_attention_without_primary_action_is_material(self):
        previous = result(action("pay", source_key="payment:1"))
        terminal = action(
            "attention:occurrence_cancelled",
            source_key="occurrence:1",
            priority=ContextualActionPriority.P0_CRITICAL,
            actionability=ContextualActionability.TERMINAL,
            mandatory=True,
        )
        current = ContextualActionResult(
            actions=(terminal,),
            primary_attention=terminal,
            primary_action=None,
            observed_at=NOW,
        )
        transition = classify_preparation_transition(previous, current)
        self.assertTrue(transition.material)
        self.assertIn("primary_action_disappeared", transition.reasons)

    def test_confirmation_and_mandatory_promotions_are_material(self):
        optional = result(action(mandatory=False, confirmation_required=False))
        required = result(action(mandatory=True, confirmation_required=True))
        transition = classify_preparation_transition(optional, required)
        self.assertTrue(transition.material)
        self.assertIn("primary_action_confirmation_required", transition.reasons)
        self.assertIn("primary_action_became_mandatory", transition.reasons)

    def test_first_observation_is_silent_baseline(self):
        transition = classify_preparation_transition(None, result(action()))
        self.assertEqual(transition.kind, PreparationTransitionKind.BASELINE)
        self.assertFalse(transition.material)

    def test_a_to_a_is_unchanged(self):
        a = result(action())
        transition = classify_preparation_transition(a, a)
        self.assertEqual(transition.kind, PreparationTransitionKind.UNCHANGED)
        self.assertFalse(transition.material)

    def test_deadline_only_p3_to_p2_is_not_notification_material(self):
        previous = result(
            action(
                priority=ContextualActionPriority.P3_PROGRESS,
                deadline=NOW + timedelta(days=2),
                deadline_state=ContextualDeadlineState.FUTURE,
                mandatory=False,
            )
        )
        current = result(
            action(
                priority=ContextualActionPriority.P2_TIME_CONSTRAINED,
                deadline=NOW + timedelta(hours=2),
                deadline_state=ContextualDeadlineState.DUE_TODAY,
                mandatory=False,
            )
        )
        self.assertNotEqual(
            contextual_action_result_signature(previous),
            contextual_action_result_signature(current),
        )
        self.assertEqual(
            proactive_notification_signature(previous),
            proactive_notification_signature(current),
        )
        self.assertTrue(deadline_only_transition(previous, current))
        transition = classify_preparation_transition(previous, current)
        self.assertTrue(transition.deadline_only)
        self.assertFalse(transition.material)

    def test_deadline_plus_real_primary_change_is_material(self):
        previous = result(
            action(
                "continue_journey",
                priority=ContextualActionPriority.P3_PROGRESS,
                deadline=NOW + timedelta(days=1),
                deadline_state=ContextualDeadlineState.FUTURE,
                mandatory=False,
            )
        )
        current = result(
            action(
                "resolve_blocker",
                priority=ContextualActionPriority.P0_CRITICAL,
                actionability=ContextualActionability.BLOCKING,
                deadline=NOW - timedelta(minutes=1),
                deadline_state=ContextualDeadlineState.OVERDUE,
                mandatory=True,
            )
        )
        self.assertTrue(classify_preparation_transition(previous, current).material)
