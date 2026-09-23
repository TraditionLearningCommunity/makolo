from __future__ import annotations

from collections.abc import Callable

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from activities.models import Activity
from activities.services import update_activity_common
from authorization.constants import PermissionCode
from authorization.services import can
from resolver.contracts import AssertionKind, EndpointKind, ResolutionStatus

from .contracts import OrchestrationContext, OrchestrationDecision, OwnerDecision


_SUPPORTED_TEXT_PREDICATES = {
    "title": "title",
    "short_description": "short_description",
    "description": "description",
}


def _text_value(assertion):
    payload = dict(assertion.candidate_payload or {})
    value = payload.get("value")
    if not isinstance(value, dict) or value.get("kind") != "text":
        return None
    text = value.get("text")
    if not isinstance(text, str):
        return None
    text = text.strip()
    return text or None


class ActivityResolvedMaterialHandler:
    """Small owner adapter for already-canonical Activity updates.

    The default policy is deliberately non-mutating: provenance/source authority
    must be established explicitly by the caller before an observed external
    fact may change canonical Activity state.
    """

    domain = "activity"

    def __init__(self, *, source_authorizer: Callable | None = None):
        self.source_authorizer = source_authorizer

    @transaction.atomic
    def __call__(self, *, material, assertion, context: OrchestrationContext) -> OwnerDecision:
        if assertion.kind is not AssertionKind.FACT:
            return OwnerDecision(
                OrchestrationDecision.REVIEW,
                "activity_assertion_kind_not_supported",
            )
        if assertion.status is not ResolutionStatus.UPDATE:
            return OwnerDecision(
                OrchestrationDecision.REVIEW,
                "activity_fact_is_not_update",
            )
        if assertion.predicate not in _SUPPORTED_TEXT_PREDICATES:
            return OwnerDecision(
                OrchestrationDecision.REVIEW,
                "activity_predicate_not_supported",
            )

        subject = assertion.subject
        if (
            subject is None
            or subject.kind is not EndpointKind.CANONICAL
            or subject.canonical_ref is None
            or subject.canonical_ref.domain != self.domain
        ):
            return OwnerDecision(
                OrchestrationDecision.DEFER,
                "activity_canonical_subject_required",
            )

        try:
            activity = (
                Activity.objects.select_for_update(of=("self",))
                .order_by()
                .get(pk=subject.canonical_ref.object_ref)
            )
        except (Activity.DoesNotExist, ValidationError, ValueError, TypeError):
            return OwnerDecision(
                OrchestrationDecision.REVIEW,
                "activity_canonical_object_not_found",
            )

        value = _text_value(assertion)
        if value is None:
            return OwnerDecision(
                OrchestrationDecision.REVIEW,
                "activity_update_value_not_supported",
            )

        field = _SUPPORTED_TEXT_PREDICATES[assertion.predicate]
        if getattr(activity, field) == value:
            return OwnerDecision(
                OrchestrationDecision.NO_ACTION,
                "activity_update_already_applied",
                operation="activity.update_common",
                applied_ref=str(activity.pk),
            )

        if activity.updated_at and activity.updated_at > material.completed_at:
            return OwnerDecision(
                OrchestrationDecision.REVIEW,
                "canonical_state_newer_than_resolution",
                operation="activity.update_common",
            )

        if self.source_authorizer is None or not self.source_authorizer(
            material=material,
            assertion=assertion,
            activity=activity,
        ):
            return OwnerDecision(
                OrchestrationDecision.REVIEW,
                "source_authority_not_established",
                operation="activity.update_common",
            )

        actor = context.actor
        if not getattr(actor, "is_authenticated", False):
            return OwnerDecision(
                OrchestrationDecision.REVIEW,
                "actor_required_for_mutation",
                operation="activity.update_common",
            )

        represented_space = context.represented_space
        if activity.space_id is not None:
            if represented_space is None:
                return OwnerDecision(
                    OrchestrationDecision.REVIEW,
                    "represented_space_required",
                    operation="activity.update_common",
                )
            if str(getattr(represented_space, "pk", "")) != str(activity.space_id):
                return OwnerDecision(
                    OrchestrationDecision.REJECT,
                    "represented_space_scope_mismatch",
                    operation="activity.update_common",
                )
        elif represented_space is not None:
            return OwnerDecision(
                OrchestrationDecision.REJECT,
                "personal_activity_cannot_use_represented_space",
                operation="activity.update_common",
            )

        if not can(actor, PermissionCode.ACTIVITY_MANAGE, activity=activity):
            return OwnerDecision(
                OrchestrationDecision.REJECT,
                "activity_manage_permission_required",
                operation="activity.update_common",
            )

        try:
            updated = update_activity_common(activity=activity, **{field: value})
        except PermissionDenied:
            return OwnerDecision(
                OrchestrationDecision.REJECT,
                "owner_authorization_rejected",
                operation="activity.update_common",
            )
        except ValidationError:
            return OwnerDecision(
                OrchestrationDecision.REJECT,
                "owner_invariant_rejected",
                operation="activity.update_common",
            )

        return OwnerDecision(
            OrchestrationDecision.APPLY,
            "activity_update_applied",
            operation="activity.update_common",
            applied_ref=str(updated.pk),
        )
