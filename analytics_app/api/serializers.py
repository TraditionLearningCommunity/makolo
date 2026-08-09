from rest_framework import serializers

from analytics_app.models import GrowthSpend
from analytics_app.permissions import user_can_manage_growth_spend


class GrowthSpendSerializer(serializers.ModelSerializer):
    channel_label = serializers.CharField(source="get_channel_display", read_only=True)
    source = serializers.CharField(source="source_label", read_only=True)

    class Meta:
        model = GrowthSpend
        fields = [
            "id",
            "organization",
            "event",
            "channel",
            "channel_label",
            "crm_campaign",
            "partner_campaign",
            "promotion",
            "loyalty_program",
            "label",
            "amount",
            "currency",
            "incurred_at",
            "notes",
            "source",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "channel_label", "source"]

    def validate(self, attrs):
        request = self.context["request"]
        organization = attrs.get("organization")
        if not organization or not user_can_manage_growth_spend(request.user, organization):
            raise serializers.ValidationError(
                {"organization": "Un rôle Finance, Owner ou Admin est requis."}
            )
        candidate = GrowthSpend(created_by=request.user, **attrs)
        try:
            candidate.full_clean()
        except Exception as exc:
            if hasattr(exc, "message_dict"):
                raise serializers.ValidationError(exc.message_dict) from exc
            raise serializers.ValidationError(str(exc)) from exc
        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        spend = GrowthSpend(created_by=request.user, **validated_data)
        spend.full_clean()
        spend.save()
        return spend
