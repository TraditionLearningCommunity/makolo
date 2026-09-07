from __future__ import annotations

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .core_models import ConversationInvitation, ConversationInvitationStatus
from .point_models import ConversationPoint, ConversationPointLifecycle
from .point_services import maybe_auto_resolve


def process_due_conversation_points(*, now=None, limit=100):
    """Advance Point and invitation time contracts from the existing Autopilot."""

    now = now or timezone.now()
    candidate_ids = list(
        ConversationPoint.objects.filter(
            lifecycle__in={ConversationPointLifecycle.OPEN, ConversationPointLifecycle.RESPONSE_CLOSED}
        )
        .filter(Q(valid_until__lte=now) | Q(lifecycle=ConversationPointLifecycle.OPEN, deadline_at__lte=now))
        .order_by("valid_until", "deadline_at", "id")
        .values_list("pk", flat=True)[: max(int(limit or 1), 1)]
    )
    stats = {"examined": 0, "responses_closed": 0, "resolved": 0, "expired": 0, "invitations_expired": 0}
    for point_id in candidate_ids:
        with transaction.atomic():
            point = ConversationPoint.objects.select_for_update().get(pk=point_id)
            stats["examined"] += 1
            if point.lifecycle not in {ConversationPointLifecycle.OPEN, ConversationPointLifecycle.RESPONSE_CLOSED}:
                continue
            if point.valid_until and point.valid_until <= now:
                point.lifecycle = ConversationPointLifecycle.EXPIRED
                point.expired_at = point.expired_at or now
                point.response_closed_at = point.response_closed_at or now
                point._allow_lifecycle_transition = True
                point.save(update_fields=["lifecycle", "expired_at", "response_closed_at", "updated_at"])
                stats["expired"] += 1
                continue
            if point.lifecycle == ConversationPointLifecycle.OPEN and point.deadline_at and point.deadline_at <= now:
                point.lifecycle = ConversationPointLifecycle.RESPONSE_CLOSED
                point.response_closed_at = point.response_closed_at or now
                point._allow_lifecycle_transition = True
                point.save(update_fields=["lifecycle", "response_closed_at", "updated_at"])
                stats["responses_closed"] += 1
                resolution = maybe_auto_resolve(point=point)
                if resolution is not None:
                    stats["resolved"] += 1

    invitation_ids = list(
        ConversationInvitation.objects.filter(
            status=ConversationInvitationStatus.PENDING,
            expires_at__isnull=False,
            expires_at__lte=now,
        )
        .order_by("expires_at", "id")
        .values_list("pk", flat=True)[: max(int(limit or 1), 1)]
    )
    for invitation_id in invitation_ids:
        with transaction.atomic():
            invitation = ConversationInvitation.objects.select_for_update().get(pk=invitation_id)
            if invitation.status != ConversationInvitationStatus.PENDING:
                continue
            if not invitation.expires_at or invitation.expires_at > now:
                continue
            invitation.status = ConversationInvitationStatus.EXPIRED
            invitation.responded_at = invitation.responded_at or now
            invitation.save(update_fields=["status", "responded_at", "updated_at"])
            stats["invitations_expired"] += 1
    return stats
