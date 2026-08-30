from __future__ import annotations

from django.utils import timezone

from subscriptions.contracts import SubscriptionStatus
from subscriptions.ongoing_services import evaluate_subscription_ongoing_requirements
from subscriptions.runtime_models import Subscription
from subscriptions.transition_models import OPEN_TRANSITION_STATUSES, SubscriptionTransition
from subscriptions.transition_services import expire_subscription_transition


def run_subscription_deadlines(*, now=None, limit=100):
    """Apply only already-due Subscription deadlines.

    The scheduler queries indexed deadline columns and then dispatches canonical,
    row-locking Subscription services. It never enumerates Profiles, Spaces or Plans.
    """
    now = now or timezone.now()
    stats = {"grace_due": 0, "transitions_expired": 0}

    grace_ids = list(
        Subscription.objects.filter(
            status=SubscriptionStatus.GRACE,
            grace_until__isnull=False,
            grace_until__lte=now,
        )
        .order_by("grace_until")
        .values_list("pk", flat=True)[:limit]
    )
    for subscription_id in grace_ids:
        evaluate_subscription_ongoing_requirements(subscription_id, now=now)
        stats["grace_due"] += 1

    transition_ids = list(
        SubscriptionTransition.objects.filter(
            status__in=OPEN_TRANSITION_STATUSES,
            expires_at__isnull=False,
            expires_at__lte=now,
        )
        .order_by("expires_at")
        .values_list("pk", flat=True)[:limit]
    )
    for transition_id in transition_ids:
        transition = SubscriptionTransition.objects.get(pk=transition_id)
        expire_subscription_transition(transition=transition, at=now)
        stats["transitions_expired"] += 1

    return stats
