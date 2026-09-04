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
)
from preparation.proactive_preparation import (
    classify_preparation_transition,
    deadline_only_transition,
    proactive_notification_signature,
)


NOW = datetime(2026, 9, 4, 10, 0, tzinfo=dt_timezone.utc)


def _result(action):
    return ContextualActionResult(
        actions=(action,),
        primary_attention=action,
        primary_action=action,
        observed_at=action.observed_at,
    )


class R3DeadlineOnlyTransitionTests(SimpleTestCase):
    def test_due_today_to_overdue_is_silent_when_only_canonical_clock_changes(self):
        due = ContextualAction(
            identity=ContextualActionIdentity(
                source_domain="payment_obligation",
                source_key="payment_obligation:1",
                action_key="pay",
                context_type="journey",
                context_id="journey:1",
            ),
            kind="readiness.payment_required",
            priority=ContextualActionPriority.P2_TIME_CONSTRAINED,
            actionability=ContextualActionability.ACTIONABLE,
            reason_codes=("payment_required",),
            label="Payer",
            summary="Paiement requis.",
            observed_at=NOW,
            deadline=NOW + timedelta(hours=1),
            deadline_state=ContextualDeadlineState.DUE_TODAY,
            mandatory=True,
        )
        overdue = replace(
            due,
            observed_at=NOW + timedelta(hours=2),
            deadline_state=ContextualDeadlineState.OVERDUE,
        )
        previous = _result(due)
        current = _result(overdue)

        self.assertEqual(
            proactive_notification_signature(previous),
            proactive_notification_signature(current),
        )
        self.assertTrue(deadline_only_transition(previous, current))
        transition = classify_preparation_transition(previous, current)
        self.assertTrue(transition.deadline_only)
        self.assertFalse(transition.material)
