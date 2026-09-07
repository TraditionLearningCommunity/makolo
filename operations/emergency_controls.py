from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.utils import OperationalError, ProgrammingError

from .models import OperationalControl, OperationalControlCode, OperationsAuditLog
from .permissions import user_can_access_operations


CONTROL_DISABLED_MESSAGES = {
    OperationalControlCode.USER_SIGNUPS: "Les nouvelles inscriptions sont temporairement suspendues par Makolo Operations.",
    OperationalControlCode.ACCESS_ISSUANCE: "L’émission de nouveaux Access est temporairement suspendue par Makolo Operations.",
    OperationalControlCode.PAYMENT_CREATION: "La création de nouveaux paiements est temporairement suspendue par Makolo Operations.",
    OperationalControlCode.AUTOPILOT: "Makolo Autopilot est temporairement suspendu par Makolo Operations.",
}


class OperationalControlDisabled(PermissionDenied):
    pass


def _validate_code(code):
    if code not in OperationalControlCode.values:
        raise ValidationError({"code": "Contrôle opérationnel inconnu."})


def is_operational_control_enabled(code) -> bool:
    """Fail open only while the control table is unavailable during deploy/migrate."""
    _validate_code(code)
    try:
        value = (
            OperationalControl.objects.filter(pk=code)
            .values_list("is_enabled", flat=True)
            .first()
        )
    except (OperationalError, ProgrammingError):
        return True
    return True if value is None else bool(value)


def require_operational_control(code) -> None:
    if is_operational_control_enabled(code):
        return
    raise OperationalControlDisabled(CONTROL_DISABLED_MESSAGES[code])


@transaction.atomic
def set_operational_control(*, code, enabled, actor, reason, incident=None) -> OperationalControl:
    _validate_code(code)
    if not user_can_access_operations(actor):
        raise PermissionDenied("Seule une autorité plateforme peut modifier les contrôles opérationnels.")
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError({"reason": "Une justification Operations est obligatoire."})

    control = OperationalControl.objects.select_for_update().get(pk=code)
    before = {
        "is_enabled": control.is_enabled,
        "incident_id": str(control.incident_id) if control.incident_id else None,
    }
    control.is_enabled = bool(enabled)
    control.reason = reason
    control.incident = incident
    control.changed_by = actor
    control.save(
        update_fields=[
            "is_enabled",
            "reason",
            "incident",
            "changed_by",
            "changed_at",
        ]
    )
    after = {
        "is_enabled": control.is_enabled,
        "incident_id": str(control.incident_id) if control.incident_id else None,
    }
    action = "operational_control.enabled" if control.is_enabled else "operational_control.disabled"
    state_label = "activé" if control.is_enabled else "suspendu"
    OperationsAuditLog.objects.create(
        actor=actor,
        action=action,
        target_type="operational_control",
        target_id=control.code,
        summary=f"{control.get_code_display()} → {state_label}",
        before=before,
        after=after,
        metadata={
            "reason": reason,
            "incident_id": str(control.incident_id) if control.incident_id else None,
        },
    )
    return control
