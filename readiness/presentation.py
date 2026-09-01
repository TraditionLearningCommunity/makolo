from .types import ReadinessStatus


READINESS_STATUS_LABELS = {
    ReadinessStatus.READY: "Tout est prêt",
    ReadinessStatus.ACTION_REQUIRED: "Action requise",
    ReadinessStatus.WAITING: "En attente",
    ReadinessStatus.BLOCKED: "Bloqué",
    ReadinessStatus.COMPLETE: "Terminé",
}


def readiness_status_label(result):
    return READINESS_STATUS_LABELS[result.status]


def readiness_next_action_label(result):
    if result.next_action:
        return result.next_action.label
    if result.status == ReadinessStatus.READY:
        return "Tout est prêt"
    if result.status == ReadinessStatus.WAITING:
        return "Aucune action maintenant"
    if result.status == ReadinessStatus.BLOCKED:
        return "Voir ce qui bloque"
    if result.status == ReadinessStatus.COMPLETE:
        return "Terminé"
    return "Voir la démarche"
