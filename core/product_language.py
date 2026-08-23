from __future__ import annotations

from dataclasses import dataclass

from access.models import AccessStatus
from commerce.models import PaymentMode
from journeys.models import WorkflowKind


ACCESS_STATUS_LABELS = {
    AccessStatus.PENDING: "En attente",
    AccessStatus.VALID: "Valide",
    AccessStatus.USED: "Utilisé",
    AccessStatus.CANCELLED: "Annulé",
    AccessStatus.REVOKED: "Révoqué",
    AccessStatus.EXPIRED: "Expiré",
    AccessStatus.TRANSFERRED: "Transféré",
}


@dataclass(frozen=True)
class ProductVocabulary:
    vertical: str
    activity_noun: str
    occurrence_noun: str
    journey_noun: str
    journey_detail_label: str
    request_noun: str
    offer_noun: str
    access_noun: str
    access_detail_label: str
    participant_noun: str
    operator_label: str
    primary_action: str

    @property
    def noun(self):
        return self.journey_noun

    @property
    def detail_label(self):
        return self.journey_detail_label


def _has_related(obj, relation_name):
    if obj is None:
        return False
    try:
        return getattr(obj, relation_name) is not None
    except Exception:
        return False


def vertical_for(activity):
    if _has_related(activity, "transport_service"):
        return "transport"
    if _has_related(activity, "event_vertical"):
        return "event"
    return "generic"


def _generic_vocabulary(workflow):
    journey = {
        WorkflowKind.PURCHASE: ("Achat", "Voir mon achat", "Voir le détail"),
        WorkflowKind.ORDER_APPROVAL: ("Demande", "Voir ma demande", "Voir ma demande"),
        WorkflowKind.RESERVATION: ("Réservation", "Voir ma réservation", "Réserver"),
        WorkflowKind.REGISTRATION: ("Inscription", "Voir mon inscription", "S’inscrire"),
        WorkflowKind.INVITATION: ("Invitation", "Voir mon invitation", "Accepter l’invitation"),
    }.get(workflow, ("Démarche", "Voir ma démarche", "Voir le détail"))
    access = {
        WorkflowKind.REGISTRATION: ("Confirmation", "Voir ma confirmation"),
        WorkflowKind.INVITATION: ("Invitation", "Voir mon invitation"),
        WorkflowKind.RESERVATION: ("Réservation", "Voir ma réservation"),
    }.get(workflow, ("Accès", "Voir mon accès"))
    return ProductVocabulary(
        vertical="generic",
        activity_noun="Activité",
        occurrence_noun="Date",
        journey_noun=journey[0],
        journey_detail_label=journey[1],
        request_noun="Demande",
        offer_noun="Tarif",
        access_noun=access[0],
        access_detail_label=access[1],
        participant_noun="Participant",
        operator_label="Proposé par",
        primary_action=journey[2],
    )


def _event_vocabulary(workflow):
    if workflow == WorkflowKind.INVITATION:
        journey = ("Invitation", "Voir mon invitation", "Accepter l’invitation")
        access = ("Invitation", "Voir mon invitation")
    elif workflow == WorkflowKind.REGISTRATION:
        journey = ("Inscription", "Voir mon inscription", "S’inscrire")
        access = ("Confirmation", "Voir ma confirmation")
    elif workflow == WorkflowKind.RESERVATION:
        journey = ("Réservation", "Voir ma réservation", "Réserver")
        access = ("Billet", "Voir mon billet")
    elif workflow == WorkflowKind.PURCHASE:
        journey = ("Achat de billet", "Voir mon achat", "Acheter le billet")
        access = ("Billet", "Voir mon billet")
    elif workflow == WorkflowKind.ORDER_APPROVAL:
        journey = ("Demande d’inscription", "Voir ma demande", "Voir ma demande")
        access = ("Billet", "Voir mon billet")
    else:
        journey = ("Démarche", "Voir ma démarche", "Voir l’événement")
        access = ("Billet", "Voir mon billet")
    return ProductVocabulary(
        vertical="event",
        activity_noun="Événement",
        occurrence_noun="Date",
        journey_noun=journey[0],
        journey_detail_label=journey[1],
        request_noun="Demande d’inscription",
        offer_noun="Type de billet",
        access_noun=access[0],
        access_detail_label=access[1],
        participant_noun="Participant",
        operator_label="Organisé par",
        primary_action=journey[2],
    )


def _transport_vocabulary(workflow):
    if workflow == WorkflowKind.PURCHASE:
        journey = ("Achat de billet", "Voir mon voyage", "Acheter le billet")
    else:
        journey = ("Réservation", "Voir ma réservation", "Réserver")
    return ProductVocabulary(
        vertical="transport",
        activity_noun="Trajet",
        occurrence_noun="Départ",
        journey_noun=journey[0],
        journey_detail_label=journey[1],
        request_noun="Demande",
        offer_noun="Tarif",
        access_noun="Billet",
        access_detail_label="Voir mon billet",
        participant_noun="Voyageur",
        operator_label="Opéré par",
        primary_action=journey[2],
    )


def vocabulary_for(*, activity=None, workflow=None):
    vertical = vertical_for(activity)
    if vertical == "transport":
        return _transport_vocabulary(workflow)
    if vertical == "event":
        return _event_vocabulary(workflow)
    return _generic_vocabulary(workflow)


def access_status_label(status):
    return ACCESS_STATUS_LABELS.get(status, status)


def participant_state_copy(*, activity, state, workflow=None):
    """Return user-facing participant-state copy without deciding domain truth."""

    vocabulary = vocabulary_for(activity=activity, workflow=workflow)
    if state == "access_valid":
        label = "Votre billet est prêt" if vocabulary.vertical == "transport" else "Vous avez accès"
        return label, vocabulary.access_detail_label
    if state == "access_used":
        return ("Billet utilisé" if vocabulary.vertical == "transport" else "Accès utilisé"), vocabulary.access_detail_label
    if state == "access_revoked":
        return "Accès révoqué", vocabulary.access_detail_label
    if state == "access_cancelled":
        return "Accès annulé", vocabulary.access_detail_label
    if state == "access_expired":
        return "Accès expiré", vocabulary.access_detail_label
    if state == "access_pending":
        return "Accès en préparation", vocabulary.access_detail_label
    if state == "request_pending":
        return "Demande envoyée", vocabulary.journey_detail_label
    if state == "capacity_held":
        return "Place retenue temporairement", vocabulary.journey_detail_label
    if state == "payment_pending":
        return "Paiement en attente", "Reprendre le paiement"
    if state == "order_pending":
        return "Commande en cours", vocabulary.journey_detail_label
    if state == "order_confirmed":
        return "Commande confirmée", vocabulary.journey_detail_label
    if state == "order_cancelled":
        return "Commande annulée", vocabulary.journey_detail_label
    if state == "order_expired":
        return "Commande expirée", vocabulary.journey_detail_label
    if state == "journey_pending":
        return "Démarche en cours", vocabulary.journey_detail_label
    return "", ""


def activity_state_label(*, activity, state):
    vocabulary = vocabulary_for(activity=activity)
    if state == "cancelled":
        return "Départ annulé" if vocabulary.vertical == "transport" else (
            "Événement annulé" if vocabulary.vertical == "event" else "Activité annulée"
        )
    if state == "completed":
        return "Départ terminé" if vocabulary.vertical == "transport" else (
            "Événement terminé" if vocabulary.vertical == "event" else "Activité terminée"
        )
    if state == "sold_out":
        return "Complet"
    if state == "closed":
        return "Indisponible"
    return "Disponible"


def payment_mode_label(mode):
    return {
        PaymentMode.NONE: "",
        PaymentMode.UPFRONT: "Paiement en ligne requis",
        PaymentMode.AFTER_APPROVAL: "Paiement requis après validation",
        PaymentMode.ON_SITE: "À payer sur place",
        PaymentMode.LATER: "Paiement ultérieur",
    }.get(mode, mode)


def occurrence_change_copy(*, activity, cancelled=False):
    vocabulary = vocabulary_for(activity=activity)
    if cancelled:
        if vocabulary.vertical == "transport":
            return "Départ annulé", "Votre départ a été annulé."
        if vocabulary.vertical == "event":
            return "Événement annulé", "L’événement a été annulé."
        return "Activité annulée", "Cette activité a été annulée."
    if vocabulary.vertical == "transport":
        return "Horaire du départ modifié", "L’horaire de votre départ a changé."
    if vocabulary.vertical == "event":
        return "Horaire de l’événement modifié", "L’horaire de l’événement a changé."
    return "Horaire modifié", "L’horaire de cette activité a changé."
