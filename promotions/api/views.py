from django.core.exceptions import PermissionDenied as DjangoPermissionDenied, ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from organizations.models import Organization, OrganizationMembership

from promotions.models import Promotion, PromotionCode, PromotionRedemption
from promotions.permissions import (
    PROMOTION_VIEW_ROLES,
    user_can_manage_promotions,
    user_can_view_promotion_financials,
    user_can_view_promotions,
)
from promotions.services import (
    create_promotion,
    create_promotion_code,
    promotion_metrics,
    toggle_promotion,
    toggle_promotion_code,
)

from .serializers import (
    PromotionCodeCreateSerializer,
    PromotionCodeSerializer,
    PromotionCreateSerializer,
    PromotionRedemptionSerializer,
    PromotionSerializer,
)


def _visible_organizations(user):
    if user.is_staff:
        return Organization.objects.all()
    ids = OrganizationMembership.objects.filter(
        user=user,
        is_active=True,
        role__in=PROMOTION_VIEW_ROLES,
    ).values_list("organization_id", flat=True)
    return Organization.objects.filter(pk__in=ids)


def _validation_response(exc):
    if isinstance(exc, DjangoValidationError):
        if hasattr(exc, "message_dict"):
            return Response(exc.message_dict, status=status.HTTP_400_BAD_REQUEST)
        return Response({"detail": exc.messages}, status=status.HTTP_400_BAD_REQUEST)
    raise exc


class PromotionListCreateAPIView(APIView):
    def get(self, request):
        queryset = Promotion.objects.filter(
            organization__in=_visible_organizations(request.user)
        ).select_related("organization", "event").prefetch_related("codes", "eligible_ticket_types")
        return Response(PromotionSerializer(queryset, many=True).data)

    def post(self, request):
        serializer = PromotionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        organization = data.pop("organization")
        if not user_can_manage_promotions(request.user, organization):
            raise PermissionDenied("Vous ne pouvez pas créer d'offre pour cette organisation.")
        try:
            promotion = create_promotion(actor=request.user, organization=organization, **data)
        except (DjangoValidationError, DjangoPermissionDenied) as exc:
            if isinstance(exc, DjangoPermissionDenied):
                raise PermissionDenied(str(exc)) from exc
            return _validation_response(exc)
        return Response(PromotionSerializer(promotion).data, status=status.HTTP_201_CREATED)


class PromotionDetailAPIView(APIView):
    def _promotion(self, request, pk):
        promotion = Promotion.objects.select_related("organization", "event").prefetch_related("codes", "eligible_ticket_types").filter(pk=pk).first()
        if not promotion:
            return None
        if not user_can_view_promotions(request.user, promotion.organization):
            raise PermissionDenied("Vous n'avez pas accès à cette offre.")
        return promotion

    def get(self, request, pk):
        promotion = self._promotion(request, pk)
        if not promotion:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(PromotionSerializer(promotion).data)


class PromotionToggleAPIView(APIView):
    def post(self, request, pk):
        promotion = Promotion.objects.select_related("organization").filter(pk=pk).first()
        if not promotion:
            return Response(status=status.HTTP_404_NOT_FOUND)
        try:
            promotion = toggle_promotion(actor=request.user, promotion=promotion)
        except DjangoPermissionDenied as exc:
            raise PermissionDenied(str(exc)) from exc
        return Response(PromotionSerializer(promotion).data)


class PromotionCodeListCreateAPIView(APIView):
    def get(self, request):
        queryset = PromotionCode.objects.filter(
            promotion__organization__in=_visible_organizations(request.user)
        ).select_related("promotion", "promotion__organization", "crm_campaign")
        promotion_id = request.query_params.get("promotion")
        if promotion_id:
            queryset = queryset.filter(promotion_id=promotion_id)
        return Response(PromotionCodeSerializer(queryset, many=True).data)

    def post(self, request):
        serializer = PromotionCodeCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        promotion = data.pop("promotion")
        if not user_can_manage_promotions(request.user, promotion.organization):
            raise PermissionDenied("Vous ne pouvez pas créer de code pour cette offre.")
        try:
            code = create_promotion_code(actor=request.user, promotion=promotion, **data)
        except (DjangoValidationError, DjangoPermissionDenied) as exc:
            if isinstance(exc, DjangoPermissionDenied):
                raise PermissionDenied(str(exc)) from exc
            return _validation_response(exc)
        return Response(PromotionCodeSerializer(code).data, status=status.HTTP_201_CREATED)


class PromotionCodeToggleAPIView(APIView):
    def post(self, request, pk):
        code = PromotionCode.objects.select_related("promotion", "promotion__organization").filter(pk=pk).first()
        if not code:
            return Response(status=status.HTTP_404_NOT_FOUND)
        try:
            code = toggle_promotion_code(actor=request.user, code=code)
        except DjangoPermissionDenied as exc:
            raise PermissionDenied(str(exc)) from exc
        return Response(PromotionCodeSerializer(code).data)


class PromotionRedemptionListAPIView(APIView):
    def get(self, request):
        queryset = PromotionRedemption.objects.filter(
            promotion__organization__in=_visible_organizations(request.user)
        ).select_related("promotion", "code", "order", "order__event")
        promotion_id = request.query_params.get("promotion")
        if promotion_id:
            queryset = queryset.filter(promotion_id=promotion_id)
        return Response(PromotionRedemptionSerializer(queryset, many=True).data)


class PromotionMetricsAPIView(APIView):
    def get(self, request, pk):
        promotion = Promotion.objects.select_related("organization").prefetch_related("codes").filter(pk=pk).first()
        if not promotion:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if not user_can_view_promotions(request.user, promotion.organization):
            raise PermissionDenied("Vous n'avez pas accès à cette offre.")
        return Response(
            promotion_metrics(
                promotion,
                include_financials=user_can_view_promotion_financials(request.user, promotion.organization),
            )
        )
