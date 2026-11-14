"""Private native API for financed subscription coverages.

A funding relationship never grants authority over a recipient's Profile, Space,
activities, dossiers, payments, or personal usage. All writes call domain services.
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.views import APIView

from organizations.models import Organization
from groups.models import Group, GroupSnapshot

from .coverage_models import SubscriptionCoverage, SubscriptionCoverageAllocation
from .coverage_services import (
    accept_coverage_allocation,
    change_coverage_status,
    create_coverage,
    decide_coverage_allocation,
    invite_coverage_beneficiary,
    select_coverage_base,
    use_personal_base,
    _require_coverage_manager,
)
from .models import PlanVersion
from .native_api_views import _private, _key
from .space_native_api_views import _space_subscription


def _error(exc):
    if isinstance(exc, DjangoPermissionDenied):
        raise PermissionDenied(str(exc)) from exc
    if isinstance(exc, DjangoValidationError):
        raise ValidationError(
            exc.message_dict if hasattr(exc, "message_dict") else exc.messages
        ) from exc
    raise exc


def _quantity(request):
    try:
        number = int(request.data.get("quantity", 0))
    except (TypeError, ValueError) as exc:
        raise ValidationError({"quantity": "Quantité entière requise."}) from exc
    if number < 1:
        raise ValidationError({"quantity": "La quantité doit être strictement positive."})
    return number


def _plan(request):
    return get_object_or_404(
        PlanVersion.objects.select_related("plan"),
        pk=request.data.get("plan_version_id"),
    )


def _coverage_payload(coverage, *, actor):
    """Financial owner projection, without the recipient's private activity."""
    allocations = coverage.allocations.select_related("group").order_by("created_at")
    from django.urls import reverse
    from payments.selectors import obligations_visible_to
    payment_links = list(coverage.billing_obligation_links.select_related("obligation"))
    visible_ids = set(
        obligations_visible_to(actor).filter(
            pk__in=[link.obligation_id for link in payment_links]
        ).values_list("pk", flat=True)
    )
    payments = [
        {
            "obligation_id": str(link.obligation_id),
            "amount": str(link.obligation.amount),
            "currency": link.obligation.currency,
            "status": link.obligation.status,
            "payment_url": (
                reverse("payments:obligation-start", kwargs={"obligation_pk": link.obligation_id})
                if link.obligation.status in {"pending", "processing"} else None
            ),
        }
        for link in payment_links if link.obligation_id in visible_ids
    ]
    return {
        "id": str(coverage.pk),
        "plan_version_id": str(coverage.plan_version_id),
        "plan_name": coverage.plan_version.name,
        "status": coverage.status,
        "purchased_quantity": coverage.purchased_quantity,
        "payments": payments,
        "starts_at": coverage.starts_at,
        "ends_at": coverage.ends_at,
        "allocations": [
            {
                "id": str(row.pk),
                "target_type": "group" if row.group_id else ("space" if row.space_id else "profile"),
                "target_id": str(row.group_id or row.space_id or row.profile_id),
                "group_parent_id": str(row.group_parent_id) if row.group_parent_id else None,
                "status": row.status,
                "selected_base": row.selected_base,
            }
            for row in allocations
        ],
    }


def _recipient_payload(allocation):
    return {
        "id": str(allocation.pk),
        "plan_name": allocation.coverage.plan_version.name,
        "status": allocation.status,
        "starts_at": allocation.starts_at,
        "ends_at": allocation.ends_at,
        "selected_base": allocation.selected_base,
        "coverage_status": allocation.coverage.status,
        "group_qualified": bool(allocation.group_parent_id),
    }


def _private_coverage(actor, coverage_id):
    coverage = get_object_or_404(
        SubscriptionCoverage.objects.select_related(
            "payer_profile", "payer_space", "plan_version"
        ),
        pk=coverage_id,
    )
    try:
        _require_coverage_manager(actor, coverage)
    except DjangoPermissionDenied as exc:
        raise Http404 from exc
    return coverage


def _buy(request, *, payer_profile=None, payer_space=None):
    version = _plan(request)
    try:
        coverage = create_coverage(
            actor=request.user, payer_profile=payer_profile, payer_space=payer_space,
            plan_version=version, purchased_quantity=_quantity(request),
            request_key=_key(request),
        )
        return _private(_coverage_payload(coverage, actor=request.user))
    except (DjangoPermissionDenied, DjangoValidationError) as exc:
        _error(exc)


def _decide(request, allocation):
    action = request.data.get("action")
    try:
        if action == "accept":
            item = accept_coverage_allocation(
                actor=request.user, allocation=allocation,
                select_base=request.data.get("select_base") is True,
            )
        elif action == "select_base":
            item = select_coverage_base(actor=request.user, allocation=allocation)
        elif action == "decline":
            item = decide_coverage_allocation(
                actor=request.user, allocation=allocation,
                reason=(request.data.get("reason") or "Refus explicite de l'attribution."),
            )
        elif action == "use_personal_base":
            if allocation.profile_id:
                use_personal_base(actor=request.user, profile=allocation.profile)
            elif allocation.space_id:
                use_personal_base(actor=request.user, space=allocation.space)
            else:
                raise ValidationError({"action": "Une population Groupe ne possède pas de BASE."})
            item = SubscriptionCoverageAllocation.objects.get(pk=allocation.pk)
        else:
            raise ValidationError({"action": "Action de couverture inconnue."})
        return _private(_recipient_payload(item))
    except (DjangoPermissionDenied, DjangoValidationError) as exc:
        _error(exc)


class PersonalCoverageAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        funded = SubscriptionCoverage.objects.filter(
            payer_profile=request.user,
        ).select_related("plan_version").order_by("-created_at")[:50]
        invitations = (
            SubscriptionCoverageAllocation.objects.filter(profile=request.user)
            .select_related("coverage__plan_version")
            .order_by("-created_at")[:50]
        )
        return _private({
            "funded": [_coverage_payload(row, actor=request.user) for row in funded],
            "received": [_recipient_payload(row) for row in invitations],
        })

    def post(self, request):
        return _buy(request, payer_profile=request.user)


class SpaceCoverageAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, slug):
        subscription = _space_subscription(request.user, slug, manage=False)
        space = subscription.space
        funded = SubscriptionCoverage.objects.filter(
            payer_space=space,
        ).select_related("plan_version").order_by("-created_at")[:50]
        received = (
            SubscriptionCoverageAllocation.objects.filter(space=space)
            .select_related("coverage__plan_version")
            .order_by("-created_at")[:50]
        )
        from .coverage_services import _require_payer_manager
        can_manage = True
        try:
            _require_payer_manager(request.user, payer_space=space)
        except DjangoPermissionDenied:
            can_manage = False
        return _private({
            "funded": [_coverage_payload(row, actor=request.user) for row in funded] if can_manage else [],
            "received": [_recipient_payload(row) for row in received],
            "can_manage": can_manage,
        })

    def post(self, request, slug):
        subscription = _space_subscription(request.user, slug, manage=True)
        return _buy(request, payer_space=subscription.space)


class CoverageManageAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, coverage_id):
        return _private(_coverage_payload(_private_coverage(request.user, coverage_id), actor=request.user))


class CoverageAllocationAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, coverage_id):
        coverage = _private_coverage(request.user, coverage_id)
        User = get_user_model()
        profile = get_object_or_404(User, pk=request.data["profile_id"]) if request.data.get("profile_id") else None
        space = get_object_or_404(Organization, pk=request.data["space_id"]) if request.data.get("space_id") else None
        group = get_object_or_404(Group, pk=request.data["group_id"]) if request.data.get("group_id") else None
        parent = (
            get_object_or_404(SubscriptionCoverageAllocation, pk=request.data["group_parent_id"])
            if request.data.get("group_parent_id") else None
        )
        snapshot = (
            get_object_or_404(GroupSnapshot, pk=request.data["group_snapshot_id"])
            if request.data.get("group_snapshot_id") else None
        )
        try:
            allocation = invite_coverage_beneficiary(
                actor=request.user, coverage=coverage, request_key=_key(request),
                profile=profile, space=space, group=group,
                group_parent=parent, group_snapshot=snapshot,
                group_policy=request.data.get("group_policy", "current_members"),
            )
            return _private({"id": str(allocation.pk), "status": allocation.status})
        except (DjangoPermissionDenied, DjangoValidationError) as exc:
            _error(exc)


class CoverageStatusAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, coverage_id):
        coverage = _private_coverage(request.user, coverage_id)
        try:
            updated = change_coverage_status(
                actor=request.user, coverage=coverage,
                status=request.data.get("status"),
                reason=request.data.get("reason") or "",
            )
            return _private(_coverage_payload(updated, actor=request.user))
        except (DjangoPermissionDenied, DjangoValidationError) as exc:
            _error(exc)


class PersonalCoverageDecisionAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, allocation_id):
        allocation = get_object_or_404(
            SubscriptionCoverageAllocation.objects.select_related("coverage__plan_version"),
            pk=allocation_id, profile=request.user,
        )
        return _decide(request, allocation)


class SpaceCoverageDecisionAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, slug, allocation_id):
        space = _space_subscription(request.user, slug, manage=True).space
        allocation = get_object_or_404(
            SubscriptionCoverageAllocation.objects.select_related("coverage__plan_version"),
            pk=allocation_id, space=space,
        )
        return _decide(request, allocation)
