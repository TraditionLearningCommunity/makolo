from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from django.urls import reverse
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from activities.models import ActivityStatus, ActivityVisibility
from authorization.constants import PermissionCode
from authorization.selectors import (
    has_direct_activity_permission,
    has_direct_space_permission,
)
from organizations.models import Organization

from .api_serializers import (
    FundingContributionSerializer,
    FundingCreateSerializer,
    FundingUpdateSerializer,
)
from .models import FundingDetails, FundingContribution
from .selectors import funding_accepts_contributions, funding_progress, public_fundings
from .services import (
    can_manage_funding,
    create_funding,
    create_funding_contribution,
    update_funding,
)


def _raise_service(exc):
    if isinstance(exc, DjangoPermissionDenied):
        raise PermissionDenied(str(exc)) from exc
    if isinstance(exc, DjangoValidationError):
        if hasattr(exc, "message_dict"):
            raise ValidationError(exc.message_dict) from exc
        raise ValidationError(getattr(exc, "messages", [str(exc)])) from exc
    raise exc


def _decimal(value):
    return str(value) if value is not None else None


def _payload(funding, actor):
    progress = funding_progress(funding)
    manage = can_manage_funding(actor, funding)
    capabilities = ["view"]
    if manage:
        capabilities.append("manage")
    if funding_accepts_contributions(funding):
        capabilities.append("contribute")
    return {
        "id": str(funding.pk),
        "activity": {
            "id": str(funding.activity_id),
            "title": funding.activity.title,
            "status": funding.activity.status,
            "visibility": funding.activity.visibility,
            "space_id": str(funding.activity.space_id) if funding.activity.space_id else None,
            "personal": funding.activity.space_id is None,
        },
        "currency": funding.currency,
        "target_amount": _decimal(funding.target_amount),
        "minimum_contribution": _decimal(funding.minimum_contribution),
        "maximum_contribution": _decimal(funding.maximum_contribution),
        "opens_at": funding.opens_at,
        "closes_at": funding.closes_at,
        "progress": {
            "raised_amount": _decimal(progress.raised_amount),
            "target_amount": _decimal(progress.target_amount),
            "remaining_amount": _decimal(progress.remaining_amount),
            "exceeded_amount": _decimal(progress.exceeded_amount),
            "target_reached": progress.target_reached,
            "percent_reached": _decimal(progress.percent_reached),
        },
        "accepts_contributions": funding_accepts_contributions(funding),
        "capabilities": capabilities,
        "links": {
            "self": f"/api/v1/funding/{funding.pk}/",
            "contribute": f"/api/v1/funding/{funding.pk}/contributions/",
        },
    }


def _can_manage_funding_direct(actor, funding):
    activity = funding.activity
    if activity.space_id is None:
        return activity.owner_profile_id == getattr(actor, "pk", None)
    if not has_direct_activity_permission(
        actor,
        activity,
        PermissionCode.ACTIVITY_MANAGE,
    ):
        return False
    return has_direct_space_permission(
        actor,
        activity.space,
        PermissionCode.FINANCE_MANAGE,
    ) or has_direct_activity_permission(
        actor,
        activity,
        PermissionCode.ACTIVITY_FINANCE_MANAGE,
    )


def _can_create_space_funding_direct(actor, space):
    return has_direct_space_permission(
        actor,
        space,
        PermissionCode.SPACE_ACTIVITIES_MANAGE,
    ) and has_direct_space_permission(
        actor,
        space,
        PermissionCode.FINANCE_MANAGE,
    )


def _managed_funding(actor, pk):
    funding = (
        FundingDetails.objects.select_related(
            "activity", "activity__space", "activity__owner_profile"
        )
        .filter(pk=pk)
        .first()
    )
    if (
        funding is None
        or not _can_manage_funding_direct(actor, funding)
        or not can_manage_funding(actor, funding)
    ):
        raise NotFound()
    return funding


class PublicFundingDetailAPIView(APIView):
    """Public, minimal Funding facts for an admitted native contribution path."""
    permission_classes = [AllowAny]

    def get(self, request, pk):
        from groups.selectors import eligible_activity_ids_for_profile

        funding = get_object_or_404(public_fundings(), pk=pk)
        if funding.activity_id not in eligible_activity_ids_for_profile(
            request.user, [funding.activity_id],
        ):
            raise NotFound()
        progress = funding_progress(funding)
        response = Response({
            "id": str(funding.pk),
            "title": funding.activity.title,
            "description": funding.activity.short_description or "",
            "currency": funding.currency,
            "minimum_contribution": _decimal(funding.minimum_contribution),
            "maximum_contribution": _decimal(funding.maximum_contribution),
            "target_amount": _decimal(funding.target_amount),
            "raised_amount": _decimal(progress.raised_amount),
            "accepts_contributions": funding_accepts_contributions(funding),
            "capabilities": ["view", "contribute"] if funding_accepts_contributions(funding) else ["view"],
            "links": {
                "contribute": reverse("funding_api:contribute", kwargs={"pk": funding.pk}),
            },
        })
        response["Cache-Control"] = "no-store"
        return response


class FundingListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        space_id = request.query_params.get("space")
        base = FundingDetails.objects.select_related(
            "activity", "activity__space", "activity__owner_profile"
        )

        if space_id:
            space = Organization.objects.filter(pk=space_id).first()
            if space is None:
                raise NotFound()
            queryset = list(
                base.filter(activity__space=space)
                .order_by("activity__title", "id")[:100]
            )
            manageable = [
                row
                for row in queryset
                if _can_manage_funding_direct(request.user, row)
                and can_manage_funding(request.user, row)
            ]
            if not manageable and not _can_create_space_funding_direct(request.user, space):
                raise NotFound()
        else:
            # Personal funding is an Activity owned by the authenticated Profile.
            # No client-supplied profile id is accepted.
            queryset = list(
                base.filter(
                    activity__space__isnull=True,
                    activity__owner_profile=request.user,
                )
                .order_by("activity__title", "id")[:100]
            )
            manageable = [
                row
                for row in queryset
                if _can_manage_funding_direct(request.user, row)
                and can_manage_funding(request.user, row)
            ]

        rows = [_payload(row, request.user) for row in manageable]
        response = Response(rows)
        response["Cache-Control"] = "private, no-store"
        return response

    def post(self, request):
        serializer = FundingCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        space_id = data.pop("space_id", None)
        space = get_object_or_404(Organization, pk=space_id) if space_id else None
        if space is not None and not _can_create_space_funding_direct(request.user, space):
            raise NotFound()
        try:
            funding = create_funding(actor=request.user, space=space, **data)
        except (DjangoPermissionDenied, DjangoValidationError) as exc:
            _raise_service(exc)
        response = Response(_payload(funding, request.user), status=201)
        response["Cache-Control"] = "private, no-store"
        return response


class FundingDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        response = Response(_payload(_managed_funding(request.user, pk), request.user))
        response["Cache-Control"] = "private, no-store"
        return response

    def patch(self, request, pk):
        funding = _managed_funding(request.user, pk)
        serializer = FundingUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        activity = funding.activity
        values = {
            "title": activity.title,
            "short_description": activity.short_description,
            "description": activity.description,
            "currency": funding.currency,
            "target_amount": funding.target_amount,
            "minimum_contribution": funding.minimum_contribution,
            "maximum_contribution": funding.maximum_contribution,
            "opens_at": funding.opens_at,
            "closes_at": funding.closes_at,
            "status": activity.status,
            "visibility": activity.visibility,
        }
        values.update(serializer.validated_data)
        try:
            funding = update_funding(actor=request.user, funding=funding, **values)
        except (DjangoPermissionDenied, DjangoValidationError) as exc:
            _raise_service(exc)
        response = Response(_payload(funding, request.user))
        response["Cache-Control"] = "private, no-store"
        return response


class FundingContributionAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        # Recovery lookup is strictly scoped to the authenticated contributor.
        # Neither Funding progress nor another contributor reveals this key.
        funding = get_object_or_404(
            FundingDetails.objects.select_related("activity"),
            pk=pk, activity__status=ActivityStatus.PUBLISHED,
        )
        if funding.activity.visibility == ActivityVisibility.PRIVATE:
            raise NotFound()
        from groups.selectors import eligible_activity_ids_for_profile

        if funding.activity_id not in eligible_activity_ids_for_profile(
            request.user, [funding.activity_id],
        ):
            raise NotFound()
        reference = (request.query_params.get("client_reference") or "").strip()
        if not reference or len(reference) > 120:
            raise ValidationError({"client_reference": "Référence requise."})
        contribution = (
            FundingContribution.objects.filter(
                funding=funding,
                contributor_profile=request.user,
                client_reference=reference,
            ).select_related("payment_obligation").first()
        )
        response = Response({
            "contribution": (
                {
                    "id": str(contribution.pk),
                    "funding_id": str(funding.pk),
                    "amount": str(contribution.amount),
                    "payment_obligation_id": str(contribution.payment_obligation_id),
                } if contribution is not None else None
            ),
        })
        response["Cache-Control"] = "private, no-store"
        return response

    def post(self, request, pk):
        funding = get_object_or_404(
            FundingDetails.objects.select_related(
                "activity", "activity__space", "activity__owner_profile"
            ),
            pk=pk,
            activity__status=ActivityStatus.PUBLISHED,
        )
        if funding.activity.visibility == ActivityVisibility.PRIVATE:
            raise NotFound()
        from groups.selectors import eligible_activity_ids_for_profile

        if funding.activity_id not in eligible_activity_ids_for_profile(
            request.user, [funding.activity_id],
        ):
            raise NotFound()

        serializer = FundingContributionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            contribution = create_funding_contribution(
                funding=funding,
                actor=request.user,
                **serializer.validated_data,
            )
        except (DjangoPermissionDenied, DjangoValidationError) as exc:
            _raise_service(exc)

        response = Response(
            {
                "id": str(contribution.pk),
                "funding_id": str(funding.pk),
                "amount": str(contribution.amount),
                "currency": contribution.currency,
                "payment_obligation_id": str(contribution.payment_obligation_id),
                "links": {
                    "payment_start_web": reverse(
                        "payments:obligation-start",
                        kwargs={"obligation_pk": contribution.payment_obligation_id},
                    )
                },
            },
            status=201,
        )
        response["Cache-Control"] = "private, no-store"
        return response
