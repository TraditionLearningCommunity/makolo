from collections import defaultdict
from dataclasses import dataclass, field

from django.db.models import Case, DateTimeField, F, Max, Prefetch, Q, When
from django.utils import timezone

from access.models import Access, AccessStatus, AccessUseResult
from commerce.models import CommerceOrder
from journeys.models import Journey, JourneyStatus, WorkflowKind
from payments.models import Payment


ACTIVE_JOURNEY_STATUSES = {
    JourneyStatus.DRAFT,
    JourneyStatus.SUBMITTED,
    JourneyStatus.PENDING_APPROVAL,
    JourneyStatus.APPROVED,
    JourneyStatus.PENDING_PAYMENT,
    JourneyStatus.CONFIRMED,
}
ACTIONABLE_JOURNEY_STATUSES = {
    JourneyStatus.DRAFT,
    JourneyStatus.PENDING_APPROVAL,
    JourneyStatus.PENDING_PAYMENT,
}
HISTORY_JOURNEY_STATUSES = {
    JourneyStatus.FULFILLED,
    JourneyStatus.REJECTED,
    JourneyStatus.CANCELLED,
    JourneyStatus.EXPIRED,
}
ACTIVE_ACCESS_STATUSES = {AccessStatus.VALID}
HISTORY_ACCESS_STATUSES = {
    AccessStatus.USED,
    AccessStatus.CANCELLED,
    AccessStatus.REVOKED,
    AccessStatus.EXPIRED,
    AccessStatus.TRANSFERRED,
}


def _authenticated(profile):
    return bool(getattr(profile, "is_authenticated", False))


@dataclass
class ParticipantStateContext:
    """Read-only participant data grouped once for Activity/Occurrence presentation."""

    profile: object | None = None
    accesses_by_activity: dict = field(default_factory=dict)
    journeys_by_activity: dict = field(default_factory=dict)

    @property
    def authenticated(self):
        return _authenticated(self.profile)

    def accesses_for(self, activity, occurrence=None):
        rows = self.accesses_by_activity.get(activity.pk, ())
        if occurrence is None:
            return list(rows)
        return [access for access in rows if access.occurrence_id in {None, occurrence.pk}]

    def journeys_for(self, activity, occurrence=None):
        rows = self.journeys_by_activity.get(activity.pk, ())
        if occurrence is None:
            return list(rows)
        return [journey for journey in rows if journey.occurrence_id in {None, occurrence.pk}]


def participant_state_context(profile, occurrences):
    context = ParticipantStateContext(profile=profile)
    if not _authenticated(profile):
        return context
    occurrences = list(occurrences)
    if not occurrences:
        return context
    activity_ids = {occurrence.activity_id for occurrence in occurrences}
    occurrence_ids = {occurrence.pk for occurrence in occurrences}
    occurrence_scope = Q(occurrence__isnull=True) | Q(occurrence_id__in=occurrence_ids)
    accesses = list(
        Access.objects.filter(beneficiary=profile, activity_id__in=activity_ids)
        .filter(occurrence_scope)
        .select_related("activity", "occurrence", "journey")
        .order_by("-created_at", "id")
    )
    orders = CommerceOrder.objects.select_related("buyer").prefetch_related(
        Prefetch("payments", queryset=Payment.objects.order_by("-created_at", "id"))
    ).order_by("-created_at", "id")
    journeys = list(
        Journey.objects.filter(beneficiary=profile, activity_id__in=activity_ids)
        .filter(occurrence_scope)
        .select_related("activity", "occurrence", "beneficiary")
        .prefetch_related("requests", "capacity_reservations__pool", Prefetch("commerce_orders", queryset=orders))
        .order_by("-created_at", "id")
    )
    accesses_by_activity = defaultdict(list)
    for access in accesses:
        accesses_by_activity[access.activity_id].append(access)
    journeys_by_activity = defaultdict(list)
    for journey in journeys:
        journeys_by_activity[journey.activity_id].append(journey)
    context.accesses_by_activity = dict(accesses_by_activity)
    context.journeys_by_activity = dict(journeys_by_activity)
    return context


def participant_journeys(profile):
    if not _authenticated(profile):
        return Journey.objects.none()
    return (
        Journey.objects.filter(beneficiary=profile)
        .select_related("activity", "activity__event_vertical", "activity__space", "activity__owner_profile", "occurrence")
        .prefetch_related(
            "occurrence__place_links__place",
            "requests",
            "transitions",
            "accesses__credentials",
            "commerce_orders__items__offer",
        )
    )


def participant_journey_search(queryset, q):
    q = (q or "").strip()
    if not q:
        return queryset
    return queryset.filter(
        Q(activity__title__icontains=q)
        | Q(activity__space__name__icontains=q)
        | Q(activity__owner_profile__first_name__icontains=q)
        | Q(activity__owner_profile__last_name__icontains=q)
        | Q(activity__owner_profile__username__icontains=q)
        | Q(occurrence__place_links__place__name__icontains=q)
        | Q(occurrence__place_links__place__locality__icontains=q)
        | Q(activity__transport_service__route__name__icontains=q)
        | Q(activity__transport_service__route__stops__place__name__icontains=q)
        | Q(activity__transport_service__route__stops__place__locality__icontains=q)
    ).distinct()


def participant_actionable_journeys(profile):
    return (
        participant_journeys(profile)
        .filter(
            Q(status__in=ACTIONABLE_JOURNEY_STATUSES)
            | Q(status=JourneyStatus.SUBMITTED, workflow=WorkflowKind.INVITATION)
        )
        .filter(accesses__isnull=True)
        .distinct()
    )


def participant_active_journeys(profile):
    return participant_journeys(profile).filter(status__in=ACTIVE_JOURNEY_STATUSES, accesses__isnull=True).distinct()


def participant_history_journeys(profile):
    return participant_journeys(profile).filter(Q(status__in=HISTORY_JOURNEY_STATUSES) | Q(accesses__isnull=False)).distinct()


def participant_unified_history_journeys(profile):
    """Closed Journeys with no Access representation of the same experience."""
    return (
        participant_journeys(profile)
        .filter(status__in=HISTORY_JOURNEY_STATUSES, accesses__isnull=True)
        .distinct()
        .order_by("-updated_at", "-created_at", "id")
    )


def participant_orders(profile):
    if not _authenticated(profile):
        return CommerceOrder.objects.none()
    return (
        CommerceOrder.objects.filter(buyer=profile)
        .select_related("journey", "journey__activity", "journey__occurrence", "payee_space", "payee_profile")
        .prefetch_related("items__offer", "payments")
    )


def _access_queryset():
    return (
        Access.objects.select_related(
            "beneficiary",
            "external_beneficiary",
            "activity",
            "activity__event_vertical",
            "activity__space",
            "activity__owner_profile",
            "occurrence",
            "journey",
            "issued_by",
        )
        .prefetch_related("occurrence__place_links__place", "credentials", "uses")
    )


def participant_accesses(profile):
    if not _authenticated(profile):
        return Access.objects.none()
    return _access_queryset().filter(beneficiary=profile)


def participant_access_search(queryset, q, *, include_external_holder=False):
    q = (q or "").strip()
    if not q:
        return queryset
    lookup = (
        Q(activity__title__icontains=q)
        | Q(activity__space__name__icontains=q)
        | Q(activity__owner_profile__first_name__icontains=q)
        | Q(activity__owner_profile__last_name__icontains=q)
        | Q(activity__owner_profile__username__icontains=q)
        | Q(occurrence__place_links__place__name__icontains=q)
        | Q(occurrence__place_links__place__locality__icontains=q)
        | Q(activity__transport_service__route__name__icontains=q)
        | Q(activity__transport_service__route__stops__place__name__icontains=q)
        | Q(activity__transport_service__route__stops__place__locality__icontains=q)
    )
    if include_external_holder:
        lookup |= Q(external_beneficiary__display_name__icontains=q)
    return queryset.filter(lookup).distinct()


def participant_accesses_visible_to_buyer(profile):
    """Access detail scope: personal rights plus rights bought in this Profile's own orders."""
    if not _authenticated(profile):
        return Access.objects.none()
    return _access_queryset().filter(Q(beneficiary=profile) | Q(journey__commerce_orders__buyer=profile)).distinct()


def participant_purchased_accesses_for_others(profile):
    if not _authenticated(profile):
        return Access.objects.none()
    return (
        _access_queryset()
        .filter(journey__commerce_orders__buyer=profile)
        .exclude(beneficiary=profile)
        .distinct()
        .order_by("-created_at", "id")
    )


def participant_active_accesses(profile, *, at=None):
    at = at or timezone.now()
    return (
        participant_accesses(profile)
        .filter(status__in=ACTIVE_ACCESS_STATUSES)
        .filter(Q(valid_until__isnull=True) | Q(valid_until__gt=at))
        .filter(Q(occurrence__isnull=True) | Q(occurrence__end_at__isnull=True) | Q(occurrence__end_at__gte=at))
        .distinct()
    )


def participant_upcoming_accesses(profile, *, at=None):
    at = at or timezone.now()
    return participant_active_accesses(profile, at=at).order_by("occurrence__start_at", "-created_at")


def participant_upcoming_engagements(profile, *, at=None):
    """Active personal Accesses that have a meaningful temporal engagement."""
    at = at or timezone.now()
    return (
        participant_active_accesses(profile, at=at)
        .filter(occurrence__isnull=False)
        .filter(Q(occurrence__end_at__isnull=True) | Q(occurrence__end_at__gte=at))
        .order_by("occurrence__start_at", "-created_at", "id")
    )


def participant_access_history(profile, *, at=None):
    at = at or timezone.now()
    return (
        participant_accesses(profile)
        .filter(
            Q(status__in=HISTORY_ACCESS_STATUSES)
            | Q(status=AccessStatus.VALID, valid_until__isnull=False, valid_until__lte=at)
            | Q(status=AccessStatus.VALID, occurrence__end_at__lt=at)
        )
        .distinct()
    )


def participant_unified_history_accesses(profile, *, at=None):
    """Historical personal Accesses ordered by the most relevant business moment."""
    at = at or timezone.now()
    return (
        participant_access_history(profile, at=at)
        .annotate(
            latest_accepted_use_at=Max(
                "uses__used_at",
                filter=Q(uses__result=AccessUseResult.ACCEPTED),
            )
        )
        .annotate(
            history_at=Case(
                When(
                    status=AccessStatus.USED,
                    latest_accepted_use_at__isnull=False,
                    then=F("latest_accepted_use_at"),
                ),
                When(
                    status=AccessStatus.VALID,
                    occurrence__end_at__lt=at,
                    then=F("occurrence__end_at"),
                ),
                When(
                    status=AccessStatus.VALID,
                    valid_until__isnull=False,
                    valid_until__lte=at,
                    then=F("valid_until"),
                ),
                default=F("updated_at"),
                output_field=DateTimeField(),
            )
        )
        .order_by("-history_at", "-created_at", "id")
    )


def participant_upcoming_occurrences(profile, *, at=None):
    at = at or timezone.now()
    return (
        participant_active_journeys(profile)
        .filter(occurrence__isnull=False, occurrence__start_at__gte=at)
        .order_by("occurrence__start_at")
    )
