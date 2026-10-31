"""Private historical Subscription transitions, read from the canonical owner.

The most recent Transition remains in SubscriptionProductView for actionable
progress; this bounded history retains older outcomes without duplicating state.
"""
from .transition_models import SubscriptionTransition


def personal_transition_history(subscription, *, offset=0, limit=20):
    if subscription.profile_id is None:
        raise ValueError("personal_transition_history requires a Profile subscription")
    rows = list(
        SubscriptionTransition.objects.filter(subscription=subscription)
        .select_related("target_plan_version")
        .order_by("-requested_at", "-pk")[offset:offset + limit + 1]
    )
    return {
        "items": [
            {
                "id": str(item.pk),
                "kind": item.kind,
                "kind_label": item.get_kind_display(),
                "status": item.status,
                "status_label": item.get_status_display(),
                "target_name": item.target_plan_version.name,
                "requested_at": item.requested_at,
                "completed_at": item.completed_at,
                "expires_at": item.expires_at,
            }
            for item in rows[:limit]
        ],
        "next_offset": offset + limit if len(rows) > limit else None,
    }
