from rest_framework import serializers

from crm.models import CommunicationCampaign
from events.models import Event
from organizations.models import Organization
from tickets.models import TicketType

from promotions.models import Promotion, PromotionCode, PromotionRedemption


class PromotionCodeSerializer(serializers.ModelSerializer):
    promotion_name = serializers.CharField(source="promotion.name", read_only=True)
    crm_campaign_name = serializers.CharField(source="crm_campaign.name", read_only=True)

    class Meta:
        model = PromotionCode
        fields = [
            "id",
            "promotion_id",
            "promotion_name",
            "code",
            "label",
            "crm_campaign_id",
            "crm_campaign_name",
            "starts_at",
            "ends_at",
            "max_redemptions",
            "is_private",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class PromotionSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    event_title = serializers.CharField(source="event.title", read_only=True)
    eligible_ticket_type_ids = serializers.PrimaryKeyRelatedField(
        source="eligible_ticket_types",
        many=True,
        read_only=True,
    )
    codes = PromotionCodeSerializer(many=True, read_only=True)

    class Meta:
        model = Promotion
        fields = [
            "id",
            "organization_id",
            "organization_name",
            "event_id",
            "event_title",
            "name",
            "description",
            "discount_type",
            "discount_value",
            "max_discount_amount",
            "min_order_amount",
            "currency",
            "eligible_ticket_type_ids",
            "starts_at",
            "ends_at",
            "max_redemptions",
            "max_redemptions_per_customer",
            "is_active",
            "codes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class PromotionCreateSerializer(serializers.Serializer):
    organization_id = serializers.PrimaryKeyRelatedField(
        source="organization", queryset=Organization.objects.all()
    )
    event_id = serializers.PrimaryKeyRelatedField(
        source="event", queryset=Event.objects.all(), required=False, allow_null=True
    )
    name = serializers.CharField(max_length=160)
    description = serializers.CharField(required=False, allow_blank=True)
    discount_type = serializers.ChoiceField(choices=["percent", "fixed"])
    discount_value = serializers.DecimalField(max_digits=12, decimal_places=2)
    max_discount_amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True
    )
    min_order_amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, default="0.00"
    )
    currency = serializers.CharField(max_length=3, required=False, allow_blank=True)
    eligible_ticket_type_ids = serializers.PrimaryKeyRelatedField(
        source="eligible_ticket_types",
        many=True,
        queryset=TicketType.objects.select_related("event", "event__organization").all(),
        required=False,
    )
    starts_at = serializers.DateTimeField(required=False, allow_null=True)
    ends_at = serializers.DateTimeField(required=False, allow_null=True)
    max_redemptions = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    max_redemptions_per_customer = serializers.IntegerField(required=False, default=1, min_value=1, max_value=100)
    is_active = serializers.BooleanField(required=False, default=True)


class PromotionCodeCreateSerializer(serializers.Serializer):
    promotion_id = serializers.PrimaryKeyRelatedField(
        source="promotion", queryset=Promotion.objects.select_related("organization", "event").all()
    )
    code = serializers.CharField(max_length=40)
    label = serializers.CharField(max_length=120, required=False, allow_blank=True)
    crm_campaign_id = serializers.PrimaryKeyRelatedField(
        source="crm_campaign",
        queryset=CommunicationCampaign.objects.select_related("organization", "event").all(),
        required=False,
        allow_null=True,
    )
    starts_at = serializers.DateTimeField(required=False, allow_null=True)
    ends_at = serializers.DateTimeField(required=False, allow_null=True)
    max_redemptions = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    is_private = serializers.BooleanField(required=False, default=False)
    is_active = serializers.BooleanField(required=False, default=True)


class PromotionRedemptionSerializer(serializers.ModelSerializer):
    code_value = serializers.CharField(source="code.code", read_only=True)
    promotion_name = serializers.CharField(source="promotion.name", read_only=True)
    order_reference = serializers.CharField(source="order.reference", read_only=True)
    event_id = serializers.UUIDField(source="order.event_id", read_only=True)

    class Meta:
        model = PromotionRedemption
        fields = [
            "id",
            "promotion_id",
            "promotion_name",
            "code_id",
            "code_value",
            "order_id",
            "order_reference",
            "event_id",
            "status",
            "subtotal_amount",
            "eligible_amount",
            "discount_amount",
            "final_amount",
            "currency",
            "reserved_at",
            "confirmed_at",
            "reversed_at",
        ]
        read_only_fields = fields
