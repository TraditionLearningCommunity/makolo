from __future__ import annotations

from django.urls import reverse
from django.utils import timezone

from notifications.models import NotificationCategory, NotificationKind
from notifications.services import create_notification

from .context import get_journey_spatiotemporal_context
from .opportunities import get_last_minute_candidates


def _category_for(journey):
    return NotificationCategory.SERVICE if journey.workflow == "service" else NotificationCategory.EVENT


def notify_significant_journey_hazards(journey, *, now=None):
    """Create idempotent notifications only for actionable canonical hazards.

    External ETA recalculations are deliberately excluded to avoid notification
    storms. The hazard key is the notification dedup key.
    """
    now = now or timezone.now()
    if journey.beneficiary_id is None:
        return []
    context = get_journey_spatiotemporal_context(journey, now=now)
    if context is None:
        return []
    created = []
    significant = {"occurrence_cancelled", "access_changed"}
    for hazard in context["hazards"]:
        if hazard.kind not in significant:
            continue
        notification = create_notification(
            recipient=journey.beneficiary,
            kind=NotificationKind.SYSTEM,
            category=_category_for(journey),
            title="Mise à jour importante de votre démarche",
            message=hazard.summary,
            action_url=reverse("core:participant-journey-detail", kwargs={"pk": journey.pk}),
            dedup_key=f"m6-hazard:{journey.pk}:{hazard.key}",
            metadata={"hazard_kind": hazard.kind, "source": hazard.source},
            journey=journey,
            activity=journey.activity,
        )
        created.append(notification)
    return created


def notify_capacity_release_opportunities(profile, *, origin=None, now=None, limit=10):
    """Notify bounded capacity-release candidates through canonical Notifications.

    This does not reserve capacity. The canonical CTA revalidates availability.
    Precise origin is never included in notification metadata or dedup keys.
    """
    now = now or timezone.now()
    notifications = []
    for opportunity in get_last_minute_candidates(profile, origin=origin, now=now, limit=limit):
        if "capacity_released" not in opportunity.reasons:
            continue
        notification = create_notification(
            recipient=profile,
            kind=NotificationKind.SYSTEM,
            category=NotificationCategory.OPPORTUNITY,
            title="Une place vient de se libérer",
            message=f"Une capacité est de nouveau disponible pour « {opportunity.activity.title} ».",
            action_url=reverse("discovery:home") + f"?focus={opportunity.occurrence.pk}",
            dedup_key=f"m6-capacity-release:{profile.pk}:{opportunity.occurrence.pk}",
            metadata={
                "activity_id": str(opportunity.activity.pk),
                "occurrence_id": str(opportunity.occurrence.pk),
                "reason": "capacity_released",
            },
            activity=opportunity.activity,
        )
        notifications.append(notification)
    return notifications
