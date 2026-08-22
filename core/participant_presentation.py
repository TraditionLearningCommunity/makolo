from dataclasses import dataclass
from zoneinfo import ZoneInfo

from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format

from access.models import AccessStatus, CredentialStatus
from activities.models import ActivityStatus, OccurrenceStatus
from capacity.models import CapacityReservationStatus
from commerce.models import CommerceOrderStatus, PaymentMode
from journeys.models import JourneyStatus, RequestStatus, WorkflowKind
from payments.models import PaymentStatus

from .product_language import (
    access_status_label,
    activity_state_label,
    participant_state_copy,
    payment_mode_label,
    vocabulary_for,
)


JOURNEY_STATUS_LABELS = {
    JourneyStatus.DRAFT: "À terminer",
    JourneyStatus.SUBMITTED: "Envoyée",
    JourneyStatus.PENDING_APPROVAL: "En attente de validation",
    JourneyStatus.APPROVED: "Approuvée",
    JourneyStatus.PENDING_PAYMENT: "Paiement requis",
    JourneyStatus.CONFIRMED: "Confirmée",
    JourneyStatus.FULFILLED: "Terminée",
    JourneyStatus.REJECTED: "Refusée",
    JourneyStatus.CANCELLED: "Annulée",
    JourneyStatus.EXPIRED: "Expirée",
}

WORKFLOW_LABELS = {
    WorkflowKind.PURCHASE: "Achat",
    WorkflowKind.ORDER_APPROVAL: "Demande",
    WorkflowKind.RESERVATION: "Réservation",
    WorkflowKind.REGISTRATION: "Inscription",
    WorkflowKind.INVITATION: "Invitation",
}

ACCESS_PRIORITY = {
    AccessStatus.VALID: 0,
    AccessStatus.USED: 1,
    AccessStatus.REVOKED: 2,
    AccessStatus.CANCELLED: 3,
    AccessStatus.EXPIRED: 4,
    AccessStatus.PENDING: 5,
    AccessStatus.TRANSFERRED: 6,
}

ACTIVE_JOURNEY_PRIORITY = {
    JourneyStatus.PENDING_PAYMENT: 0,
    JourneyStatus.PENDING_APPROVAL: 1,
    JourneyStatus.APPROVED: 2,
    JourneyStatus.SUBMITTED: 3,
    JourneyStatus.CONFIRMED: 4,
    JourneyStatus.DRAFT: 5,
}


@dataclass(frozen=True)
class OccurrenceTiming:
    date_label: str
    time_label: str
    compact_label: str
    timezone_label: str


@dataclass(frozen=True)
class ParticipantActivityState:
    availability: str
    availability_label: str
    participant_state: str
    label: str | None
    secondary_label: str | None
    primary_action: str | None
    primary_url: str | None
    visual_variant: str
    expires_at: object | None = None


def occurrence_timing(occurrence):
    if occurrence is None:
        return None
    zone = ZoneInfo(occurrence.timezone)
    local_start = occurrence.start_at.astimezone(zone)
    date_label = date_format(local_start, "l d F Y")
    time_label = local_start.strftime("%H:%M")
    compact_label = f"{date_format(local_start, 'D d M')} · {time_label}"
    return OccurrenceTiming(
        date_label=date_label,
        time_label=time_label,
        compact_label=compact_label,
        timezone_label=occurrence.timezone,
    )


def journey_status_label(status):
    return JOURNEY_STATUS_LABELS.get(status, status)


def active_credential(access):
    return next((c for c in access.credentials.all() if c.status == CredentialStatus.ACTIVE), None)


def next_participant_action(journey):
    vocabulary = vocabulary_for(activity=journey.activity, workflow=journey.workflow)
    if journey.status == JourneyStatus.DRAFT:
        return vocabulary.primary_action
    if journey.status == JourneyStatus.PENDING_APPROVAL:
        return "Attendre la validation"
    if journey.status == JourneyStatus.PENDING_PAYMENT:
        return "Payer"
    if journey.workflow == WorkflowKind.INVITATION and journey.status == JourneyStatus.SUBMITTED:
        return "Répondre à l’invitation"
    if journey.workflow == WorkflowKind.RESERVATION and journey.status == JourneyStatus.CONFIRMED:
        return vocabulary.access_detail_label
    if journey.status in {JourneyStatus.CONFIRMED, JourneyStatus.FULFILLED} and journey.accesses.all():
        return vocabulary.access_detail_label
    if journey.status == JourneyStatus.REJECTED:
        return "Demande refusée"
    if journey.status == JourneyStatus.EXPIRED:
        return "Démarche expirée"
    if journey.status == JourneyStatus.CANCELLED:
        return "Démarche annulée"
    return vocabulary.journey_detail_label


def journey_progress(journey):
    vocabulary = vocabulary_for(activity=journey.activity, workflow=journey.workflow)
    submitted = journey.status not in {JourneyStatus.DRAFT}
    confirmed = journey.status in {JourneyStatus.CONFIRMED, JourneyStatus.FULFILLED}
    has_access = bool(journey.accesses.all())
    if vocabulary.vertical == "transport":
        return [("Voyage choisi", submitted), ("Réservation confirmée", confirmed), ("Billet disponible", has_access)]
    if journey.workflow == WorkflowKind.REGISTRATION:
        return [("Inscription envoyée", submitted), ("Inscription confirmée", confirmed), (f"{vocabulary.access_noun} disponible", has_access)]
    if journey.workflow == WorkflowKind.RESERVATION:
        return [("Réservation envoyée", submitted), ("Réservation confirmée", confirmed), (f"{vocabulary.access_noun} disponible", has_access)]
    if journey.workflow == WorkflowKind.INVITATION:
        return [("Invitation reçue", True), ("Invitation acceptée", confirmed), (f"{vocabulary.access_noun} disponible", has_access)]
    return [("Démarche envoyée", submitted), ("Confirmation reçue", confirmed), (f"{vocabulary.access_noun} disponible", has_access)]


def _global_availability(*, activity, occurrence, availability_state, availability_label, now):
    if activity.status == ActivityStatus.CANCELLED or (
        occurrence is not None and occurrence.status == OccurrenceStatus.CANCELLED
    ):
        return "cancelled", activity_state_label(activity=activity, state="cancelled")
    if activity.status in {ActivityStatus.COMPLETED, ActivityStatus.ARCHIVED} or (
        occurrence is not None and occurrence.status == OccurrenceStatus.COMPLETED
    ):
        return "completed", activity_state_label(activity=activity, state="completed")
    if occurrence is not None and occurrence.end_at and occurrence.end_at <= now:
        return "completed", activity_state_label(activity=activity, state="completed")
    if availability_state == "sold_out":
        return "sold_out", activity_state_label(activity=activity, state="sold_out")
    if availability_state in {"closed", "unavailable"}:
        return "closed", availability_label or activity_state_label(activity=activity, state="closed")
    return availability_state or "available", availability_label or activity_state_label(activity=activity, state="available")


def _logical_access_state(access, *, now):
    if access.status == AccessStatus.VALID and access.valid_until and access.valid_until <= now:
        return "access_expired"
    return {
        AccessStatus.VALID: "access_valid",
        AccessStatus.USED: "access_used",
        AccessStatus.REVOKED: "access_revoked",
        AccessStatus.CANCELLED: "access_cancelled",
        AccessStatus.EXPIRED: "access_expired",
        AccessStatus.PENDING: "access_pending",
        AccessStatus.TRANSFERRED: "access_expired",
    }.get(access.status, "access_pending")


def _access_sort_key(access, *, now):
    logical = _logical_access_state(access, now=now)
    logical_rank = {
        "access_valid": 0,
        "access_used": 1,
        "access_revoked": 2,
        "access_cancelled": 3,
        "access_expired": 4,
        "access_pending": 5,
    }.get(logical, 9)
    return (logical_rank, -access.created_at.timestamp(), str(access.pk))


def _journey_sort_key(journey):
    return (
        ACTIVE_JOURNEY_PRIORITY.get(journey.status, 20),
        -journey.created_at.timestamp(),
        str(journey.pk),
    )


def _state(
    *,
    availability,
    availability_label,
    participant_state="none",
    label=None,
    secondary_label=None,
    primary_action=None,
    primary_url=None,
    visual_variant="neutral",
    expires_at=None,
):
    return ParticipantActivityState(
        availability=availability,
        availability_label=availability_label,
        participant_state=participant_state,
        label=label,
        secondary_label=secondary_label,
        primary_action=primary_action,
        primary_url=primary_url,
        visual_variant=visual_variant,
        expires_at=expires_at,
    )


def resolve_participant_activity_state(
    *,
    profile,
    activity,
    occurrence=None,
    context=None,
    availability_state="available",
    availability_label="Disponible",
    acquisition_label=None,
    acquisition_url=None,
    detail_url=None,
    now=None,
):
    """Resolve read-only participant presentation from canonical bounded contexts.

    The function performs no mutations. Pass a batched ParticipantStateContext for
    list surfaces so the resolver itself remains query-free.
    """

    now = now or timezone.now()
    availability, global_label = _global_availability(
        activity=activity,
        occurrence=occurrence,
        availability_state=availability_state,
        availability_label=availability_label,
        now=now,
    )
    authenticated = bool(getattr(profile, "is_authenticated", False))
    if not authenticated or context is None:
        if availability in {"cancelled", "completed"}:
            return _state(
                availability=availability,
                availability_label=global_label,
                visual_variant="danger" if availability == "cancelled" else "neutral",
            )
        if availability == "sold_out":
            return _state(
                availability=availability,
                availability_label=global_label,
                primary_action="Voir le détail" if detail_url else None,
                primary_url=detail_url,
                visual_variant="neutral",
            )
        return _state(
            availability=availability,
            availability_label=global_label,
            primary_action=acquisition_label,
            primary_url=acquisition_url,
            visual_variant="brand",
        )

    accesses = sorted(context.accesses_for(activity, occurrence), key=lambda row: _access_sort_key(row, now=now))
    if accesses:
        access = accesses[0]
        personal = _logical_access_state(access, now=now)
        label, action = participant_state_copy(
            activity=activity,
            state=personal,
            workflow=getattr(access.journey, "workflow", None),
        )
        variant = "success" if personal == "access_valid" else (
            "danger" if personal in {"access_revoked", "access_cancelled"} else "neutral"
        )
        return _state(
            availability=availability,
            availability_label=global_label,
            participant_state=personal,
            label=label,
            primary_action=action,
            primary_url=reverse("core:participant-access-detail", kwargs={"pk": access.pk}),
            visual_variant=variant,
        )

    journeys = sorted(context.journeys_for(activity, occurrence), key=_journey_sort_key)
    for journey in journeys:
        orders = list(journey.commerce_orders.all())
        orders.sort(key=lambda row: (-row.created_at.timestamp(), str(row.pk)))
        for order in orders:
            logical_order_status = order.status
            if order.status == CommerceOrderStatus.PENDING and order.expires_at and order.expires_at <= now:
                logical_order_status = CommerceOrderStatus.EXPIRED
            if logical_order_status == CommerceOrderStatus.PENDING:
                online_payment = (
                    order.buyer_id == getattr(profile, "pk", None)
                    and order.total > 0
                    and order.payment_mode in {PaymentMode.UPFRONT, PaymentMode.AFTER_APPROVAL, PaymentMode.LATER}
                )
                if online_payment:
                    payments = list(order.payments.all())
                    active_payment = next(
                        (
                            payment
                            for payment in payments
                            if payment.status in {PaymentStatus.PENDING, PaymentStatus.PROCESSING}
                        ),
                        None,
                    )
                    label, action = participant_state_copy(
                        activity=activity,
                        state="payment_pending",
                        workflow=journey.workflow,
                    )
                    payment_url = (
                        reverse("payments:detail", kwargs={"pk": active_payment.pk})
                        if active_payment
                        else reverse("payments:commerce-start", kwargs={"order_pk": order.pk})
                    )
                    return _state(
                        availability=availability,
                        availability_label=global_label,
                        participant_state="payment_pending",
                        label=label,
                        primary_action=action,
                        primary_url=payment_url,
                        visual_variant="warning",
                        expires_at=order.expires_at,
                    )

        holds = [
            hold
            for hold in journey.capacity_reservations.all()
            if hold.status == CapacityReservationStatus.HELD
            and (hold.expires_at is None or hold.expires_at > now)
        ]
        if holds:
            hold = min(
                holds,
                key=lambda row: (row.expires_at or timezone.datetime.max.replace(tzinfo=timezone.get_current_timezone()), row.created_at, str(row.pk)),
            )
            label, action = participant_state_copy(
                activity=activity,
                state="capacity_held",
                workflow=journey.workflow,
            )
            secondary = None
            if hold.expires_at:
                zone = ZoneInfo(occurrence.timezone) if occurrence is not None else timezone.get_current_timezone()
                secondary = f"Jusqu’à {hold.expires_at.astimezone(zone).strftime('%H:%M')}"
            return _state(
                availability=availability,
                availability_label=global_label,
                participant_state="capacity_held",
                label=label,
                secondary_label=secondary,
                primary_action=action,
                primary_url=reverse("core:participant-journey-detail", kwargs={"pk": journey.pk}),
                visual_variant="warning",
                expires_at=hold.expires_at,
            )

        pending_request = next(
            (
                request
                for request in journey.requests.all()
                if request.status == RequestStatus.PENDING
                and request.requester_id == getattr(profile, "pk", None)
                and (request.expires_at is None or request.expires_at > now)
            ),
            None,
        )
        if pending_request:
            label, action = participant_state_copy(
                activity=activity,
                state="request_pending",
                workflow=journey.workflow,
            )
            return _state(
                availability=availability,
                availability_label=global_label,
                participant_state="request_pending",
                label=label,
                primary_action=action,
                primary_url=reverse("core:participant-journey-detail", kwargs={"pk": journey.pk}),
                visual_variant="warning",
                expires_at=pending_request.expires_at,
            )

        orders = list(journey.commerce_orders.all())
        orders.sort(key=lambda row: (-row.created_at.timestamp(), str(row.pk)))
        if orders:
            order = orders[0]
            order_state = {
                CommerceOrderStatus.DRAFT: "order_pending",
                CommerceOrderStatus.PENDING: "order_pending",
                CommerceOrderStatus.CONFIRMED: "order_confirmed",
                CommerceOrderStatus.CANCELLED: "order_cancelled",
                CommerceOrderStatus.EXPIRED: "order_expired",
                CommerceOrderStatus.REFUNDED: "order_cancelled",
            }.get(order.status, "order_pending")
            if order.status == CommerceOrderStatus.PENDING and order.expires_at and order.expires_at <= now:
                order_state = "order_expired"
            label, action = participant_state_copy(
                activity=activity,
                state=order_state,
                workflow=journey.workflow,
            )
            return _state(
                availability=availability,
                availability_label=global_label,
                participant_state=order_state,
                label=label,
                primary_action=action,
                primary_url=reverse("core:participant-journey-detail", kwargs={"pk": journey.pk}),
                visual_variant="neutral" if order_state in {"order_cancelled", "order_expired"} else "warning",
                expires_at=order.expires_at,
            )

        if journey.status in ACTIVE_JOURNEY_PRIORITY:
            label, action = participant_state_copy(
                activity=activity,
                state="journey_pending",
                workflow=journey.workflow,
            )
            if journey.status == JourneyStatus.PENDING_PAYMENT:
                label = "Paiement requis"
            elif journey.status == JourneyStatus.PENDING_APPROVAL:
                label = "Demande en attente"
            elif journey.status == JourneyStatus.DRAFT:
                label = "Démarche commencée"
            return _state(
                availability=availability,
                availability_label=global_label,
                participant_state="journey_pending",
                label=label,
                primary_action=action,
                primary_url=reverse("core:participant-journey-detail", kwargs={"pk": journey.pk}),
                visual_variant="warning",
                expires_at=journey.expires_at,
            )

    if availability in {"cancelled", "completed"}:
        return _state(
            availability=availability,
            availability_label=global_label,
            visual_variant="danger" if availability == "cancelled" else "neutral",
        )
    if availability == "sold_out":
        return _state(
            availability=availability,
            availability_label=global_label,
            primary_action="Voir le détail" if detail_url else None,
            primary_url=detail_url,
            visual_variant="neutral",
        )
    return _state(
        availability=availability,
        availability_label=global_label,
        primary_action=acquisition_label,
        primary_url=acquisition_url,
        visual_variant="brand",
    )
