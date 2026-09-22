from access.models import AccessStatus
from journeys.models import JourneyStatus

from .participant_presentation import access_status_label, journey_status_label


def history_access_label(access):
    if access.status == AccessStatus.USED:
        return "Participé"
    if access.status == AccessStatus.CANCELLED:
        return "Annulé"
    if access.status == AccessStatus.REVOKED:
        return "Révoqué"
    if access.status == AccessStatus.TRANSFERRED:
        return "Transféré"
    if access.status == AccessStatus.EXPIRED:
        return "Expiré"
    if access.status == AccessStatus.VALID:
        return "Terminé"
    return access_status_label(access.status)


def history_journey_label(journey):
    labels = {
        JourneyStatus.FULFILLED: "Démarche terminée",
        JourneyStatus.REJECTED: "Demande refusée",
        JourneyStatus.CANCELLED: "Démarche annulée",
        JourneyStatus.EXPIRED: "Démarche expirée",
    }
    return labels.get(journey.status, journey_status_label(journey.status))
