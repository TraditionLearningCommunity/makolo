"""Idempotent native entry into an existing Service Journey owner workflow.

The database unique key is a hash of actor, Service and client operation key.
It is not a global Permission/Mandate and does not make a Journey public.
"""
from __future__ import annotations

import hashlib
import re
from uuid import UUID

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError

from .models import ServiceJourneyContext, ServicePlanTemplateStatus
from .services import create_service_journey


_OPERATION_KEY_RE = re.compile(r"^[A-Za-z0-9._:-]{16,128}$")


class ServiceStartIdempotencyConflict(Exception):
    """A previously accepted key was reused for a different operation."""


def _fingerprint(*, service, actor, operation_key: str) -> str:
    if not isinstance(operation_key, str) or not _OPERATION_KEY_RE.fullmatch(
        operation_key
    ):
        raise ValidationError(
            "Idempotency-Key doit comporter 16 à 128 caractères autorisés."
        )
    if not getattr(actor, "is_authenticated", False):
        raise PermissionDenied("Un Profile authentifié est nécessaire.")
    material = (
        f"services.start.v1:{actor.pk}:{service.pk}:{operation_key}"
    ).encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def _replay_or_conflict(
    *, context, service, actor, objective: str, opportunity=None,
    opportunity_id=None,
):
    existing = context.journey
    if not isinstance(objective, str):
        raise ServiceStartIdempotencyConflict(
            "Cette clé ne correspond pas aux données de la requête."
        )
    requested_opportunity_id = getattr(opportunity, "pk", None)
    if opportunity_id is not None:
        try:
            requested_opportunity_id = (
                UUID(str(opportunity_id)) if opportunity_id else None
            )
        except (ValueError, TypeError, AttributeError):
            raise ServiceStartIdempotencyConflict(
                "Une Opportunity différente a été fournie."
            ) from None
    if (
        existing.initiated_by_id != actor.pk
        or existing.beneficiary_id != actor.pk
        or existing.activity_id != service.activity_id
        or context.objective != (objective or "").strip()
        or context.opportunity_id != requested_opportunity_id
    ):
        raise ServiceStartIdempotencyConflict(
            "Cette clé d'opération a déjà été utilisée avec d'autres données."
        )
    return existing, False


def replay_native_start_if_exists(
    *, service, actor, operation_key: str, objective="", opportunity_id=None,
):
    """Return the accepted result even if new creation rules changed later.

    The caller must still authorize viewing the Service. An existing operation
    is checked against the original actor, Service, objective and Opportunity,
    not against a newly published revision.
    """
    key = _fingerprint(service=service, actor=actor, operation_key=operation_key)
    existing = (
        ServiceJourneyContext.objects.select_related("journey")
        .filter(start_operation_fingerprint=key)
        .first()
    )
    if existing is None:
        return None
    return _replay_or_conflict(
        context=existing, service=service, actor=actor,
        objective=objective, opportunity_id=opportunity_id,
    )


def start_service_journey_idempotently(
    *, service, actor, operation_key: str, objective="", opportunity=None,
):
    """Start once; replay returns the original Journey with no new mutation.

    Caller must enforce public Service visibility, Group eligibility, and
    validated published Opportunity selection. This owner helper still
    enforces actor binding and never accepts a beneficiary ID from clients.
    """
    key = _fingerprint(service=service, actor=actor, operation_key=operation_key)
    existing = (
        ServiceJourneyContext.objects.select_related("journey")
        .filter(start_operation_fingerprint=key)
        .first()
    )
    if existing is not None:
        return _replay_or_conflict(
            context=existing, service=service, actor=actor,
            objective=objective, opportunity=opportunity,
        )

    # Keep template selection aligned with the current Services Web flow.
    template = (
        service.plan_templates
        .filter(status=ServicePlanTemplateStatus.PUBLISHED)
        .order_by("-version", "-created_at")
        .first()
    )
    try:
        journey = create_service_journey(
            service=service,
            initiated_by=actor,
            beneficiary=actor,
            objective=objective,
            template=template,
            opportunity=opportunity,
            start_operation_fingerprint=key,
        )
    except (IntegrityError, ValidationError):
        # In a racing replay the competing transaction may have committed the
        # unique fingerprint. Do not hide unrelated domain validation errors.
        existing = (
            ServiceJourneyContext.objects.select_related("journey")
            .filter(start_operation_fingerprint=key)
            .first()
        )
        if existing is None:
            raise
        return _replay_or_conflict(
            context=existing, service=service, actor=actor,
            objective=objective, opportunity=opportunity,
        )
    return journey, True
