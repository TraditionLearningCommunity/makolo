from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from partners.permissions import user_can_view_partner_finance
from partners.selectors import (
    get_campaigns_visible_to,
    get_commissions_visible_to,
    get_partners_visible_to,
    get_payouts_visible_to,
    get_referral_codes_visible_to,
)
from partners.services import build_partner_metrics, cancel_payout, mark_payout_paid

from .serializers import (
    CampaignSerializer,
    CommissionSerializer,
    PartnerMetricsSerializer,
    PartnerSerializer,
    PayoutSerializer,
    ReferralCodeSerializer,
)
from .write_serializers import (
    CampaignCreateSerializer,
    PartnerCreateSerializer,
    PayoutCreateSerializer,
    PayoutPaidSerializer,
    ReferralCodeCreateSerializer,
)


def _raise_service_error(exc):
    if isinstance(exc, DjangoPermissionDenied):
        raise PermissionDenied(str(exc)) from exc
    if isinstance(exc, DjangoValidationError):
        if hasattr(exc, "message_dict"):
            raise ValidationError(exc.message_dict) from exc
        raise ValidationError(exc.messages) from exc
    raise exc


class PartnerListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(PartnerSerializer(get_partners_visible_to(request.user), many=True).data)

    def post(self, request):
        serializer = PartnerCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        try:
            partner = serializer.save()
        except (DjangoPermissionDenied, DjangoValidationError) as exc:
            _raise_service_error(exc)
        return Response(PartnerSerializer(partner).data, status=status.HTTP_201_CREATED)


class CampaignListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(CampaignSerializer(get_campaigns_visible_to(request.user), many=True).data)

    def post(self, request):
        serializer = CampaignCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        try:
            campaign = serializer.save()
        except (DjangoPermissionDenied, DjangoValidationError) as exc:
            _raise_service_error(exc)
        return Response(CampaignSerializer(campaign).data, status=status.HTTP_201_CREATED)


class ReferralCodeListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(ReferralCodeSerializer(get_referral_codes_visible_to(request.user), many=True).data)

    def post(self, request):
        serializer = ReferralCodeCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        try:
            referral = serializer.save()
        except (DjangoPermissionDenied, DjangoValidationError) as exc:
            _raise_service_error(exc)
        return Response(ReferralCodeSerializer(referral).data, status=status.HTTP_201_CREATED)


class CommissionListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(CommissionSerializer(get_commissions_visible_to(request.user), many=True).data)


class PayoutListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(PayoutSerializer(get_payouts_visible_to(request.user), many=True).data)

    def post(self, request):
        serializer = PayoutCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        try:
            payout = serializer.save()
        except (DjangoPermissionDenied, DjangoValidationError) as exc:
            _raise_service_error(exc)
        return Response(PayoutSerializer(payout).data, status=status.HTTP_201_CREATED)


class PayoutMarkPaidAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        payout = get_object_or_404(get_payouts_visible_to(request.user), pk=pk)
        serializer = PayoutPaidSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            payout = mark_payout_paid(
                payout=payout,
                actor=request.user,
                reference=serializer.validated_data.get("reference", ""),
            )
        except (DjangoPermissionDenied, DjangoValidationError) as exc:
            _raise_service_error(exc)
        return Response(PayoutSerializer(payout).data)


class PayoutCancelAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        payout = get_object_or_404(get_payouts_visible_to(request.user), pk=pk)
        try:
            payout = cancel_payout(payout=payout, actor=request.user)
        except (DjangoPermissionDenied, DjangoValidationError) as exc:
            _raise_service_error(exc)
        return Response(PayoutSerializer(payout).data)


class PartnerMetricsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        partner = get_object_or_404(get_partners_visible_to(request.user), pk=pk)
        finance_visible = user_can_view_partner_finance(request.user, partner.organization) or partner.user_id == request.user.pk
        payload = build_partner_metrics(partner, finance_visible=finance_visible)
        return Response(PartnerMetricsSerializer(payload).data)
