from __future__ import annotations

from dataclasses import dataclass

from commerce.models import PaymentMode
from journeys.models import WorkflowKind


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

    # Participant templates historically used these concise names. They remain
    # presentation aliases only; the canonical wording is defined above.
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
