from django.shortcuts import get_object_or_404
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
from partners.services import build_partner_metrics

from .serializers import (
    CampaignSerializer,
    CommissionSerializer,
    PartnerMetricsSerializer,
    PartnerSerializer,
    PayoutSerializer,
    ReferralCodeSerializer,
)


class PartnerListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(PartnerSerializer(get_partners_visible_to(request.user), many=True).data)


class CampaignListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(CampaignSerializer(get_campaigns_visible_to(request.user), many=True).data)


class ReferralCodeListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(ReferralCodeSerializer(get_referral_codes_visible_to(request.user), many=True).data)


class CommissionListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(CommissionSerializer(get_commissions_visible_to(request.user), many=True).data)


class PayoutListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(PayoutSerializer(get_payouts_visible_to(request.user), many=True).data)


class PartnerMetricsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        partner = get_object_or_404(get_partners_visible_to(request.user), pk=pk)
        finance_visible = user_can_view_partner_finance(request.user, partner.organization) or partner.user_id == request.user.pk
        payload = build_partner_metrics(partner, finance_visible=finance_visible)
        return Response(PartnerMetricsSerializer(payload).data)
