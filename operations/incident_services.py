from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from .models import IncidentSeverity, IncidentStatus, OperationsIncident
from .permissions import user_can_manage_incident
from .services import audit_action


TERMINAL_INCIDENT_STATUSES = {IncidentStatus.RESOLVED, IncidentStatus.DISMISSED}
_UNSET = object()


def _require_incident_manage(actor, incident):
    if not user_can_manage_incident(actor, incident):
        raise PermissionDenied("Vous n’avez pas l’autorité Operations requise dans ce contexte.")


@transaction.atomic
def create_incident(*, actor, **data):
    incident = OperationsIncident(opened_by=actor, **data)
    # full_clean normalizes Event/Occurrence -> Activity/Space before the
    # authorization decision, without creating any canonical object.
    incident.full_clean()
    _require_incident_manage(actor, incident)
    incident.save()
    audit_action(
        actor=actor,
        action="incident.created",
        target_type="operations_incident",
        target_id=incident.pk,
        summary=f"Incident créé: {incident.title}",
        after={
            "status": incident.status,
            "severity": incident.severity,
            "category": incident.category,
            "activity_id": str(incident.activity_id) if incident.activity_id else None,
            "occurrence_id": str(incident.occurrence_id) if incident.occurrence_id else None,
        },
    )
    return incident


@transaction.atomic
def update_incident(
    *, incident, actor, status=None, severity=None, assigned_to=_UNSET, resolution=None
):
    incident = (
        OperationsIncident.objects.select_for_update(of=("self",))
        .select_related("organization", "activity", "occurrence")
        .order_by()
        .get(pk=incident.pk)
    )
    _require_incident_manage(actor, incident)
    before = {
        "status": incident.status,
        "severity": incident.severity,
        "assigned_to": str(incident.assigned_to_id) if incident.assigned_to_id else None,
        "resolved_at": incident.resolved_at.isoformat() if incident.resolved_at else None,
    }
    now = timezone.now()
    if status is not None:
        if status not in IncidentStatus.values:
            raise ValidationError({"status": "Statut d'incident invalide."})
        incident.status = status
        if status in {IncidentStatus.INVESTIGATING, IncidentStatus.MONITORING} and not incident.acknowledged_at:
            incident.acknowledged_at = now
        if status in TERMINAL_INCIDENT_STATUSES:
            incident.resolved_at = incident.resolved_at or now
        else:
            incident.resolved_at = None
    if severity is not None:
        if severity not in IncidentSeverity.values:
            raise ValidationError({"severity": "Sévérité invalide."})
        incident.severity = severity
    if assigned_to is not _UNSET:
        incident.assigned_to = assigned_to
    if resolution is not None:
        incident.resolution = resolution.strip()
    incident.full_clean()
    _require_incident_manage(actor, incident)
    incident.save()
    after = {
        "status": incident.status,
        "severity": incident.severity,
        "assigned_to": str(incident.assigned_to_id) if incident.assigned_to_id else None,
        "resolved_at": incident.resolved_at.isoformat() if incident.resolved_at else None,
    }
    audit_action(
        actor=actor,
        action="incident.updated",
        target_type="operations_incident",
        target_id=incident.pk,
        summary=f"Incident mis à jour: {incident.title}",
        before=before,
        after=after,
    )
    return incident
