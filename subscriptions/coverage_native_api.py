"""Authenticated funded coverage API. Every write delegates to canonical services."""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_datetime
from django.utils import timezone

from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from authorization.constants import PermissionCode
from authorization.services import can
from groups.models import Group, GroupSnapshot
from organizations.models import Organization

from .coverage_models import SubscriptionCoverage, SubscriptionCoverageAllocation
from .coverage_presentation import beneficiary_coverages, coverage_card, payer_coverages
from .coverage_services import (
    accept_coverage_allocation, change_coverage_status, create_coverage,
    decide_coverage_allocation, invite_coverage_beneficiary, select_coverage_base,
    use_personal_base,
)
from .models import PlanVersion


def _private(value):
    response = Response(value)
    response["Cache-Control"] = "private, no-store"
    return response


def _raise_native(exc):
    if isinstance(exc, DjangoPermissionDenied):
        raise PermissionDenied(str(exc)) from exc
    if isinstance(exc, DjangoValidationError):
        raise ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages) from exc
    raise exc


def _idempotency_key(data):
    key = data.get("idempotency_key")
    if not isinstance(key, str) or not 8 <= len(key.strip()) <= 128:
        raise ValidationError({"idempotency_key": "Une référence stable de 8 à 128 caractères est obligatoire."})
    return key.strip()


def _lookup(model, value, *, field="id", **filters):
    if value is None or value == "":
        raise ValidationError({field: "Identifiant requis."})
    try:
        return get_object_or_404(model, pk=value, **filters)
    except (ValueError, DjangoValidationError, TypeError) as exc:
        raise ValidationError({field: "Identifiant invalide."}) from exc


def _valid_date(value, name):
    if not isinstance(value, str):
        raise ValidationError({name: "Date ISO 8601 requise."})
    date = parse_datetime(value)
    if date is None or timezone.is_naive(date):
        raise ValidationError({name: "Date ISO 8601 avec fuseau horaire requise."})
    return date


def _positive_quantity(value):
    if isinstance(value, bool):
        raise ValidationError({"quantity": "Un entier positif est requis."})
    try:
        count = int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValidationError({"quantity": "Un entier positif est requis."}) from exc
    if str(value) != str(count) or count < 1:
        raise ValidationError({"quantity": "Un entier positif est requis."})
    return count


def _get_context(request, slug=None, *, manage=False):
    if slug is None:
        return {"payer_profile": request.user}, request.user
    space = get_object_or_404(Organization, slug=slug)
    permission = PermissionCode.SPACE_SUBSCRIPTION_MANAGE if manage else PermissionCode.SPACE_SUBSCRIPTION_VIEW
    if not can(request.user, permission, space=space):
        raise PermissionDenied("Droit de consultation ou de gestion de l'abonnement de l'Espace requis.")
    return {"payer_space": space}, space


def _coverage_for_context(request, coverage_id, slug=None):
    filters, _ = _get_context(request, slug, manage=True)
    return get_object_or_404(
        SubscriptionCoverage.objects.select_related(
            "payer_profile", "payer_space", "plan_version__plan",
        ),
        pk=coverage_id, **filters,
    )


def _allocation_for_beneficiary(request, allocation_id, slug=None):
    if slug is None:
        return get_object_or_404(
            SubscriptionCoverageAllocation.objects.select_related("coverage"),
            pk=allocation_id, profile=request.user,
        )
    _, space = _get_context(request, slug, manage=True)
    return get_object_or_404(
        SubscriptionCoverageAllocation.objects.select_related("coverage"),
        pk=allocation_id, space=space,
    )


class CoverageCollectionAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, slug=None):
        filters, subject = _get_context(request, slug)
        financed = payer_coverages(
            profile=filters.get("payer_profile"), space=filters.get("payer_space"),
        )
        return _private({
            "financed": financed,
            # Keep the existing native funded-coverage contract for clients
            # already consuming this endpoint. Both keys contain exactly the
            # same payer-scoped rows; neither includes recipient-private work.
            "funded": financed,
            "received": beneficiary_coverages(subject=subject),
        })

    def post(self, request, slug=None):
        filters, _ = _get_context(request, slug, manage=True)
        data = request.data
        version = _lookup(PlanVersion, data.get("plan_version_id"), field="plan_version_id")
        previous = None
        if data.get("renewal_of"):
            previous = _lookup(
                SubscriptionCoverage, data["renewal_of"], field="renewal_of", **filters,
            )
        start = _valid_date(data["starts_at"], "starts_at") if data.get("starts_at") is not None else None
        end = _valid_date(data["ends_at"], "ends_at") if data.get("ends_at") is not None else None
        if previous is not None and start is None:
            start = previous.ends_at
        try:
            coverage = create_coverage(
                actor=request.user, plan_version=version,
                purchased_quantity=_positive_quantity(data.get("quantity")),
                starts_at=start, ends_at=end,
                request_key=_idempotency_key(data),
                renewal_of=previous, **filters,
            )
        except (DjangoValidationError, DjangoPermissionDenied) as exc:
            _raise_native(exc)
        return _private(coverage_card(coverage, include_allocations=True))


class CoverageAllocationCreateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, coverage_id, slug=None):
        coverage = _coverage_for_context(request, coverage_id, slug)
        data = request.data
        typed = data.get("target_type")
        target_id = data.get("target_id")
        if typed not in {"profile", "space", "group"}:
            raise ValidationError({"target_type": "Choisir profile, space ou group."})
        if typed == "profile":
            destination = {"profile": _lookup(get_user_model(), target_id, field="target_id")}
        elif typed == "space":
            destination = {"space": _lookup(Organization, target_id, field="target_id")}
        else:
            destination = {"group": _lookup(Group, target_id, field="target_id")}
        parent = (
            _lookup(SubscriptionCoverageAllocation, data["group_parent_id"], field="group_parent_id", coverage=coverage)
            if data.get("group_parent_id") else None
        )
        snapshot = (
            _lookup(GroupSnapshot, data["group_snapshot_id"], field="group_snapshot_id")
            if data.get("group_snapshot_id") else None
        )
        try:
            allocation = invite_coverage_beneficiary(
                actor=request.user, coverage=coverage, request_key=_idempotency_key(data),
                group_parent=parent, group_snapshot=snapshot,
                group_policy=data.get("group_policy", "current_members"),
                **destination,
            )
        except (DjangoValidationError, DjangoPermissionDenied) as exc:
            _raise_native(exc)
        return _private({"id": str(allocation.pk), "status": allocation.status})


class CoverageStateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, coverage_id, slug=None):
        coverage = _coverage_for_context(request, coverage_id, slug)
        reason = request.data.get("reason", "")
        if not isinstance(reason, str):
            raise ValidationError({"reason": "Une justification textuelle est requise."})
        try:
            updated = change_coverage_status(
                actor=request.user, coverage=coverage,
                status=request.data.get("status"),
                reason=reason,
            )
        except (DjangoValidationError, DjangoPermissionDenied) as exc:
            _raise_native(exc)
        return _private({"id": str(updated.pk), "status": updated.status})


class AllocationBeneficiaryAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, allocation_id, operation, slug=None):
        allocation = _allocation_for_beneficiary(request, allocation_id, slug)
        try:
            if operation == "accept":
                result = accept_coverage_allocation(
                    actor=request.user, allocation=allocation,
                    select_base=request.data.get("select_base") is True,
                )
            elif operation == "select-base":
                result = select_coverage_base(actor=request.user, allocation=allocation)
            elif operation == "decline":
                result = decide_coverage_allocation(
                    actor=request.user, allocation=allocation,
                    reason=request.data.get("reason") or "Attribution refusée par le bénéficiaire.",
                )
            else:
                raise Http404
        except (DjangoValidationError, DjangoPermissionDenied) as exc:
            _raise_native(exc)
        return _private({
            "id": str(result.pk),
            "status": result.status,
            "selected_base": result.selected_base,
        })


class UsePersonalBaseAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, slug=None):
        _, subject = _get_context(request, slug, manage=slug is not None)
        try:
            if slug is None:
                use_personal_base(actor=request.user, profile=subject)
            else:
                use_personal_base(actor=request.user, space=subject)
        except (DjangoValidationError, DjangoPermissionDenied) as exc:
            _raise_native(exc)
        return _private({"selected_base": "personal"})
