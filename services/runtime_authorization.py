from __future__ import annotations

from functools import wraps

from django.core.exceptions import PermissionDenied

from authorization.constants import PermissionCode
from authorization.services import can as authorization_can
from journeys.models import WorkflowKind
from journeys.service_authorization import (
    CASE_SCOPE_VIEW_ALL,
    CASE_SCOPE_VIEW_ASSIGNED,
    service_case_scope,
)


def _require_case_scope(actor, journey):
    if service_case_scope(actor, journey) not in {CASE_SCOPE_VIEW_ALL, CASE_SCOPE_VIEW_ASSIGNED}:
        raise PermissionDenied("Accès opérateur refusé à ce dossier Services.")


def _require_case_manage(actor, journey):
    _require_case_scope(actor, journey)
    if not authorization_can(actor, PermissionCode.ACTIVITY_SERVICES_CASES_MANAGE, activity=journey.activity):
        raise PermissionDenied("La gestion de ce dossier Services n'est pas autorisée.")


def _require_outcomes(actor, journey):
    _require_case_scope(actor, journey)
    if not authorization_can(actor, PermissionCode.ACTIVITY_SERVICES_OUTCOMES_MANAGE, activity=journey.activity):
        raise PermissionDenied("La gestion des soumissions/résultats Services n'est pas autorisée.")


def install_services_runtime_authorization():
    from . import services as service_services
    from . import t33_services
    from payments import obligation_services

    if getattr(service_services, "_t34b_runtime_authorization_installed", False):
        return

    # services.services historically asked for activity.manage for Service configuration.
    # Keep the module code stable while translating only that legacy check to the
    # canonical Activity-scoped Services configuration permission.
    original_service_can = service_services.can

    def service_module_can(actor, permission_code, space=None, *, group=None, activity=None, at=None):
        if permission_code == PermissionCode.ACTIVITY_MANAGE and activity is not None:
            return authorization_can(
                actor,
                PermissionCode.ACTIVITY_SERVICES_CONFIGURE,
                activity=activity,
                at=at,
            )
        return original_service_can(actor, permission_code, space, group=group, activity=activity, at=at)

    service_services.can = service_module_can

    def ensure_case_operator(actor, journey):
        _require_case_manage(actor, journey)

    def ensure_submission_owner_or_operator(actor, journey):
        if getattr(actor, "is_authenticated", False) and journey.beneficiary_id == actor.pk:
            return
        _require_outcomes(actor, journey)

    t33_services._ensure_case_operator = ensure_case_operator
    t33_services._ensure_submission_owner_or_operator = ensure_submission_owner_or_operator

    original_record_service_outcome = t33_services.record_service_outcome

    @wraps(original_record_service_outcome)
    def record_service_outcome(*args, **kwargs):
        context = kwargs["context"]
        actor = kwargs["actor"]
        _require_outcomes(actor, context.journey)
        return original_record_service_outcome(*args, **kwargs)

    t33_services.record_service_outcome = record_service_outcome

    original_evidence_reviewer = obligation_services._ensure_evidence_reviewer

    def ensure_evidence_reviewer(actor, obligation):
        journey = obligation.journey
        if getattr(journey, "workflow", None) != WorkflowKind.SERVICE:
            return original_evidence_reviewer(actor, obligation)
        _require_case_scope(actor, journey)
        if not authorization_can(
            actor,
            PermissionCode.ACTIVITY_SERVICES_PAYMENT_EVIDENCE_VERIFY,
            activity=journey.activity,
        ):
            raise PermissionDenied("La vérification des preuves de paiement Services n'est pas autorisée.")

    obligation_services._ensure_evidence_reviewer = ensure_evidence_reviewer
    service_services._t34b_runtime_authorization_installed = True
