from django import template

from access.models import AccessUseResult
from core.product_language import vocabulary_for


register = template.Library()


@register.filter
def participant_access_use_label(access_use):
    result = access_use.result
    vocabulary = vocabulary_for(activity=access_use.access.activity)
    if result == AccessUseResult.ACCEPTED:
        return "Accès accepté"
    if result == AccessUseResult.NOT_YET_VALID:
        return "Présenté avant l’ouverture du contrôle"
    if result == AccessUseResult.ALREADY_USED:
        return "Nouvelle présentation · Déjà utilisé"
    if result == AccessUseResult.EXPIRED:
        return "Billet expiré"
    if result == AccessUseResult.REVOKED:
        return "Billet révoqué"
    if result == AccessUseResult.CANCELLED:
        return "Billet annulé"
    if result == AccessUseResult.WRONG_ACTIVITY:
        return "Présenté pour une autre activité"
    if result == AccessUseResult.WRONG_OCCURRENCE:
        if vocabulary.vertical == "transport":
            return "Présenté pour un autre départ"
        if vocabulary.vertical == "event":
            return "Présenté pour une autre date"
        return "Présenté pour une autre occurrence"
    if result == AccessUseResult.INVALID_CREDENTIAL:
        return "QR invalide ou non reconnu"
    return access_use.get_result_display()
