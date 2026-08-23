from __future__ import annotations

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from activities.models import Activity, ActivityStatus, Occurrence, OccurrenceStatus
from authorization.constants import PermissionCode
from authorization.services import can
from capacity.models import CapacityPool
from capacity.services import commit_capacity, reserve_capacity
from journeys.models import JourneyStatus, WorkflowKind
from journeys.services import create_journey

from .models import Access, AccessStatus
from .services import issue_access


_BLOCKED_ACTIVITY_STATUSES = {
    ActivityStatus.CANCELLED,
    ActivityStatus.COMPLETED,
    ActivityStatus.ARCHIVED,
}
_BLOCKED_OCCURRENCE_STATUSES = {
    OccurrenceStatus.CANCELLED,
    OccurrenceStatus.COMPLETED,
}
_ACTIVE_ACCESS_STATUSES = {
    AccessStatus.PENDING,
    AccessStatus.VALID,
}


def _lock_beneficiary(beneficiary):
    manager = beneficiary.__class__._default_manager
    return manager.select_for_update().order_by().get(pk=beneficiary.pk)


def _finite_admission_pools(activity):
    """Non-commercial finite pools that govern physical admission.

    Offer-backed pools describe inventory for a commercial selection. A direct
    grant does not choose or buy an Offer, so consuming those pools would invent a
    commercial action. Generic non-Offer pools, including Event-wide capacity,
    are admission quotas and must still be respected.
    """

    return CapacityPool.objects.filter(
        activity=activity,
        is_active=True,
        total_quantity__isnull=False,
        offers__isnull=True,
    ).distinct()


def _applicable_admission_pools(*, activity, occurrence):
    queryset = _finite_admission_pools(activity)
    if occurrence is None:
        if queryset.filter(occurrence__isnull=False).exists():
            raise ValidationError(
                "Sélectionnez une session : cette activité possède une capacité limitée par session."
            )
        queryset = queryset.filter(occurrence__isnull=True)
    else:
        queryset = queryset.filter(Q(occurrence__isnull=True) | Q(occurrence=occurrence))
    return list(queryset.order_by("pk"))


def _validate_grant_scope(*, actor, beneficiary, activity, occurrence, now):
    if not getattr(actor, "is_authenticated", False):
        raise PermissionDenied("Une autorité authentifiée est requise.")
    if not can(actor, PermissionCode.ACTIVITY_ACCESS_MANAGE, activity=activity):
        raise PermissionDenied("Vous ne pouvez pas accorder un accès pour cette activité.")
    if beneficiary is None or not getattr(beneficiary, "is_active", False):
        raise ValidationError("Le bénéficiaire doit être un compte Makolo actif.")
    if activity.status in _BLOCKED_ACTIVITY_STATUSES:
        raise ValidationError("Cette activité ne peut plus recevoir de nouveaux accès.")
    if occurrence is not None:
        if occurrence.activity_id != activity.pk:
            raise ValidationError("La session sélectionnée appartient à une autre activité.")
        if occurrence.status in _BLOCKED_OCCURRENCE_STATUSES:
            raise ValidationError("Cette session ne peut plus recevoir de nouveaux accès.")
        if occurrence.end_at is not None and occurrence.end_at <= now:
            raise ValidationError("Cette session est déjà terminée.")


def _active_duplicate(*, beneficiary, activity, occurrence, now):
    queryset = Access.objects.select_for_update(of=("self",)).filter(
        beneficiary=beneficiary,
        activity=activity,
        status__in=_ACTIVE_ACCESS_STATUSES,
    )
    if occurrence is None:
        queryset = queryset.filter(occurrence__isnull=True)
    else:
        # An Activity-wide right already covers the requested occurrence.
        queryset = queryset.filter(Q(occurrence__isnull=True) | Q(occurrence=occurrence))
    queryset = queryset.filter(
        Q(status=AccessStatus.PENDING)
        | Q(valid_until__isnull=True)
        | Q(valid_until__gt=now)
    )
    return queryset.order_by("created_at", "pk").first()


def _consume_admission_capacity(*, actor, beneficiary, activity, occurrence, pools, now):
    if not pools:
        return None

    journey = create_journey(
        initiated_by=actor,
        beneficiary=beneficiary,
        activity=activity,
        occurrence=occurrence,
        workflow=WorkflowKind.REGISTRATION,
        status=JourneyStatus.FULFILLED,
    )
    # CapacityReservation requires a real Journey. This operator-initiated,
    # already-fulfilled process exists only when a physical admission quota must
    # be consumed; it is not a purchase and creates no CommerceOrder or Payment.
    journey.fulfilled_at = now
    journey.save(update_fields=["fulfilled_at", "updated_at"])

    for pool in pools:
        reservation = reserve_capacity(
            pool=pool,
            journey=journey,
            quantity=1,
            source_key="manual-access",
        )
        commit_capacity(reservation=reservation, now=now)
    return journey


@transaction.atomic
def grant_access_manually(*, actor, beneficiary, activity, occurrence=None, reason="") -> Access:
    """Grant a canonical Access directly, with human authority and no commerce.

    This orchestration is deliberately separate from issue_access(): system flows
    may issue rights without ACTIVITY_ACCESS_MANAGE, while this human mutation must
    prove contextual authority. No Ticket, CommerceOrder or Payment is created.
    """

    now = timezone.now()
    activity = Activity.objects.select_for_update(of=("self",)).order_by().get(pk=activity.pk)
    if occurrence is not None:
        occurrence = Occurrence.objects.select_for_update(of=("self",)).order_by().get(pk=occurrence.pk)
    beneficiary = _lock_beneficiary(beneficiary)

    _validate_grant_scope(
        actor=actor,
        beneficiary=beneficiary,
        activity=activity,
        occurrence=occurrence,
        now=now,
    )

    existing = _active_duplicate(
        beneficiary=beneficiary,
        activity=activity,
        occurrence=occurrence,
        now=now,
    )
    if existing is not None:
        raise ValidationError("Cette personne possède déjà un accès actif pour cette activité.")

    pools = _applicable_admission_pools(activity=activity, occurrence=occurrence)
    _consume_admission_capacity(
        actor=actor,
        beneficiary=beneficiary,
        activity=activity,
        occurrence=occurrence,
        pools=pools,
        now=now,
    )

    return issue_access(
        beneficiary=beneficiary,
        activity=activity,
        occurrence=occurrence,
        journey=None,
        issued_by=actor,
        status=AccessStatus.VALID,
        create_credential=True,
        audit_reason=(reason or "").strip()[:240],
    )
