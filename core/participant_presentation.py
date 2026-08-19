from dataclasses import dataclass

from access.models import AccessStatus, CredentialStatus
from commerce.models import PaymentMode
from journeys.models import JourneyStatus, WorkflowKind


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

ACCESS_STATUS_LABELS = {
    AccessStatus.PENDING: "En attente",
    AccessStatus.VALID: "Valide",
    AccessStatus.USED: "Utilisé",
    AccessStatus.CANCELLED: "Annulé",
    AccessStatus.REVOKED: "Révoqué",
    AccessStatus.EXPIRED: "Expiré",
    AccessStatus.TRANSFERRED: "Transféré",
}

PAYMENT_MODE_LABELS = {
    PaymentMode.NONE: "",
    PaymentMode.UPFRONT: "Paiement en ligne requis",
    PaymentMode.AFTER_APPROVAL: "Paiement requis après validation",
    PaymentMode.ON_SITE: "À payer sur place",
    PaymentMode.LATER: "Paiement ultérieur",
}

WORKFLOW_LABELS = {
    WorkflowKind.PURCHASE: "Achat",
    WorkflowKind.ORDER_APPROVAL: "Demande",
    WorkflowKind.RESERVATION: "Réservation",
    WorkflowKind.REGISTRATION: "Inscription",
    WorkflowKind.INVITATION: "Invitation",
}


@dataclass(frozen=True)
class ParticipantVocabulary:
    noun: str
    detail_label: str
    access_noun: str
    access_detail_label: str


def _is_event(activity):
    try:
        return activity.event_vertical is not None
    except Exception:
        return False


def vocabulary_for(*, activity, workflow=None):
    if workflow == WorkflowKind.INVITATION:
        return ParticipantVocabulary("Invitation", "Voir mon invitation", "Invitation", "Voir mon invitation")
    if workflow == WorkflowKind.RESERVATION:
        return ParticipantVocabulary("Réservation", "Voir ma réservation", "Réservation", "Voir ma réservation")
    if workflow == WorkflowKind.REGISTRATION:
        return ParticipantVocabulary("Inscription", "Voir mon inscription", "Confirmation", "Voir ma confirmation")
    if _is_event(activity):
        return ParticipantVocabulary("Événement", "Voir ma démarche", "Billet", "Voir mon billet")
    return ParticipantVocabulary("Démarche", "Voir ma démarche", "Accès", "Voir mon accès")


def journey_status_label(status):
    return JOURNEY_STATUS_LABELS.get(status, status)


def access_status_label(status):
    return ACCESS_STATUS_LABELS.get(status, status)


def payment_mode_label(mode):
    return PAYMENT_MODE_LABELS.get(mode, mode)


def active_credential(access):
    return next((c for c in access.credentials.all() if c.status == CredentialStatus.ACTIVE), None)


def next_participant_action(journey):
    if journey.status == JourneyStatus.DRAFT:
        return "Continuer"
    if journey.status == JourneyStatus.PENDING_APPROVAL:
        return "Attendre la validation"
    if journey.status == JourneyStatus.PENDING_PAYMENT:
        return "Payer"
    if journey.workflow == WorkflowKind.INVITATION and journey.status in {JourneyStatus.SUBMITTED, JourneyStatus.APPROVED}:
        return "Répondre à l’invitation"
    if journey.workflow == WorkflowKind.RESERVATION and journey.status == JourneyStatus.CONFIRMED:
        return "Voir ma réservation"
    if journey.status in {JourneyStatus.CONFIRMED, JourneyStatus.FULFILLED} and journey.accesses.all():
        return vocabulary_for(activity=journey.activity, workflow=journey.workflow).access_detail_label
    if journey.status == JourneyStatus.REJECTED:
        return "Demande refusée"
    if journey.status == JourneyStatus.EXPIRED:
        return "Démarche expirée"
    if journey.status == JourneyStatus.CANCELLED:
        return "Démarche annulée"
    return "Voir le détail"


def journey_progress(journey):
    steps = []
    submitted = journey.status not in {JourneyStatus.DRAFT}
    confirmed = journey.status in {JourneyStatus.CONFIRMED, JourneyStatus.FULFILLED}
    has_access = bool(journey.accesses.all())
    if journey.workflow == WorkflowKind.REGISTRATION:
        steps = [("Inscription envoyée", submitted), ("Inscription confirmée", confirmed), ("Accès disponible", has_access)]
    elif journey.workflow == WorkflowKind.RESERVATION:
        steps = [("Réservation envoyée", submitted), ("Réservation confirmée", confirmed), ("Accès disponible", has_access)]
    elif journey.workflow == WorkflowKind.INVITATION:
        steps = [("Invitation reçue", True), ("Invitation acceptée", confirmed), ("Accès disponible", has_access)]
    else:
        steps = [("Démarche envoyée", submitted), ("Confirmation reçue", confirmed), ("Accès disponible", has_access)]
    return steps
