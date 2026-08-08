from rest_framework import serializers

from partners.models import AffiliateCampaign, Partner, PartnerCommission, PartnerPayout, ReferralCode
from partners.services import build_partner_metrics


class PartnerSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    display_name = serializers.CharField(read_only=True)

    class Meta:
        model = Partner
        fields = [
            "id",
            "organization",
            "organization_name",
            "kind",
            "status",
            "name",
            "public_label",
            "display_name",
            "email",
            "phone",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class CampaignSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    event_title = serializers.CharField(source="event.title", read_only=True)
    event_slug = serializers.CharField(source="event.slug", read_only=True)
    is_active_now = serializers.BooleanField(read_only=True)

    class Meta:
        model = AffiliateCampaign
        fields = [
            "id",
            "organization",
            "organization_name",
            "event",
            "event_title",
            "event_slug",
            "name",
            "status",
            "commission_type",
            "commission_value",
            "commission_currency",
            "attribution_window_days",
            "starts_at",
            "ends_at",
            "is_active_now",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class ReferralCodeSerializer(serializers.ModelSerializer):
    partner_name = serializers.CharField(source="partner.display_name", read_only=True)
    event_slug = serializers.CharField(source="campaign.event.slug", read_only=True)
    is_usable = serializers.BooleanField(read_only=True)
    referral_path = serializers.SerializerMethodField()

    class Meta:
        model = ReferralCode
        fields = [
            "id",
            "campaign",
            "partner",
            "partner_name",
            "event_slug",
            "code",
            "is_active",
            "is_usable",
            "commission_type_override",
            "commission_value_override",
            "referral_path",
            "created_at",
        ]
        read_only_fields = fields

    def get_referral_path(self, obj):
        return f"/partners/r/{obj.code}/"


class CommissionSerializer(serializers.ModelSerializer):
    partner_name = serializers.CharField(source="partner.display_name", read_only=True)
    event_title = serializers.CharField(source="campaign.event.title", read_only=True)
    order_reference = serializers.CharField(source="order.reference", read_only=True)

    class Meta:
        model = PartnerCommission
        fields = [
            "id",
            "partner",
            "partner_name",
            "event_title",
            "order_reference",
            "amount",
            "currency",
            "commission_type",
            "commission_value",
            "status",
            "earned_at",
            "reversed_at",
            "paid_at",
        ]
        read_only_fields = fields


class PayoutSerializer(serializers.ModelSerializer):
    partner_name = serializers.CharField(source="partner.display_name", read_only=True)

    class Meta:
        model = PartnerPayout
        fields = [
            "id",
            "organization",
            "partner",
            "partner_name",
            "currency",
            "amount",
            "status",
            "reference",
            "paid_at",
            "created_at",
        ]
        read_only_fields = fields


class PartnerMetricsSerializer(serializers.Serializer):
    visits = serializers.IntegerField()
    attributed_orders = serializers.IntegerField()
    confirmed_orders = serializers.IntegerField()
    conversion_percent = serializers.FloatField(allow_null=True)
    active_codes = serializers.IntegerField()
    commissions = serializers.ListField()
