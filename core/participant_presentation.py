from dataclasses import dataclass
from zoneinfo import ZoneInfo

from django.utils.formats import date_format

from access.models import CredentialStatus
from journeys.models import JourneyStatus, WorkflowKind

from .product_language import access_status_label, payment_mode_label, vocabulary_for


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


@dataclass(frozen=True)
class OccurrenceTiming:
    date_label: str
    time_label: str
    compact_label: str
    timezone_label: str


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
