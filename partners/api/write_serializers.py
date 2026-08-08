from django.contrib.auth import get_user_model
from rest_framework import serializers

from events.models import Event
from organizations.models import Organization
from partners.models import AffiliateCampaign, CommissionType, Partner, PartnerKind, ReferralCode
from partners.services import create_campaign, create_partner, create_payout, create_referral_code


class PartnerCreateSerializer(serializers.Serializer):
    organization_id = serializers.PrimaryKeyRelatedField(source="organization", queryset=Organization.objects.all())
    name = serializers.CharField(max_length=180)
    public_label = serializers.CharField(max_length=180, required=False, allow_blank=True)
    kind = serializers.ChoiceField(choices=PartnerKind.choices, default=PartnerKind.AMBASSADOR)
    email = serializers.EmailField(required=False, allow_blank=True)
    phone = serializers.CharField(max_length=40, required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    account_email = serializers.EmailField(required=False, allow_blank=True, write_only=True)

    def validate(self, attrs):
        account_email = (attrs.pop("account_email", "") or "").strip().lower()
        linked_user = None
        if account_email:
            User = get_user_model()
            linked_user = User.objects.filter(email__iexact=account_email, is_active=True).first()
            if not linked_user:
                raise serializers.ValidationError({"account_email": "Aucun compte Makolo actif ne correspond à cet e-mail."})
            email = (attrs.get("email") or "").strip().lower()
            if email and email != linked_user.email.lower():
                raise serializers.ValidationError({"email": "L’e-mail de contact doit correspondre au compte Makolo lié."})
            attrs["email"] = linked_user.email
        attrs["linked_user"] = linked_user
        return attrs

    def create(self, validated_data):
        actor = self.context["request"].user
        public_label = validated_data.pop("public_label", "")
        linked_user = validated_data.pop("linked_user", None)
        partner = create_partner(actor=actor, user=linked_user, **validated_data)
        if public_label:
            partner.public_label = public_label
            partner.save(update_fields=["public_label", "updated_at"])
        return partner


class CampaignCreateSerializer(serializers.Serializer):
    organization_id = serializers.PrimaryKeyRelatedField(source="organization", queryset=Organization.objects.all())
    event_id = serializers.PrimaryKeyRelatedField(source="event", queryset=Event.objects.all())
    name = serializers.CharField(max_length=180)
    status = serializers.ChoiceField(choices=["draft", "active", "paused", "ended"], default="draft")
    commission_type = serializers.ChoiceField(choices=CommissionType.choices)
    commission_value = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0)
    commission_currency = serializers.CharField(max_length=3, default="USD")
    attribution_window_days = serializers.IntegerField(min_value=1, max_value=90, default=30)
    starts_at = serializers.DateTimeField(required=False, allow_null=True)
    ends_at = serializers.DateTimeField(required=False, allow_null=True)

    def create(self, validated_data):
        return create_campaign(actor=self.context["request"].user, **validated_data)


class ReferralCodeCreateSerializer(serializers.Serializer):
    campaign_id = serializers.PrimaryKeyRelatedField(source="campaign", queryset=AffiliateCampaign.objects.all())
    partner_id = serializers.PrimaryKeyRelatedField(source="partner", queryset=Partner.objects.all())
    code = serializers.CharField(max_length=40, required=False, allow_blank=True)
    commission_type_override = serializers.ChoiceField(choices=CommissionType.choices, required=False, allow_blank=True)
    commission_value_override = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0, required=False, allow_null=True)

    def create(self, validated_data):
        return create_referral_code(actor=self.context["request"].user, **validated_data)


class PayoutCreateSerializer(serializers.Serializer):
    partner_id = serializers.PrimaryKeyRelatedField(source="partner", queryset=Partner.objects.all())
    currency = serializers.CharField(max_length=3)
    reference = serializers.CharField(max_length=120, required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)

    def create(self, validated_data):
        return create_payout(actor=self.context["request"].user, **validated_data)


class PayoutPaidSerializer(serializers.Serializer):
    reference = serializers.CharField(max_length=120, required=False, allow_blank=True)
