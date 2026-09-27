from rest_framework import serializers

from activities.models import ActivityStatus, ActivityVisibility


class FundingCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=220)
    short_description = serializers.CharField(max_length=320, required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)
    space_id = serializers.UUIDField(required=False, allow_null=True)
    currency = serializers.CharField(max_length=3, default="USD")
    target_amount = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, allow_null=True, min_value=0.01)
    minimum_contribution = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, allow_null=True, min_value=0.01)
    maximum_contribution = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, allow_null=True, min_value=0.01)
    opens_at = serializers.DateTimeField(required=False, allow_null=True)
    closes_at = serializers.DateTimeField(required=False, allow_null=True)
    status = serializers.ChoiceField(choices=ActivityStatus.choices, default=ActivityStatus.DRAFT)
    visibility = serializers.ChoiceField(choices=ActivityVisibility.choices, default=ActivityVisibility.PUBLIC)

    def validate_currency(self, value):
        value = value.strip().upper()
        if len(value) != 3 or not value.isalpha():
            raise serializers.ValidationError("Utilisez un code devise ISO de trois lettres.")
        return value

    def validate(self, attrs):
        minimum = attrs.get("minimum_contribution")
        maximum = attrs.get("maximum_contribution")
        if minimum is not None and maximum is not None and maximum < minimum:
            raise serializers.ValidationError({
                "maximum_contribution": "Le maximum ne peut pas être inférieur au minimum."
            })
        opens_at = attrs.get("opens_at")
        closes_at = attrs.get("closes_at")
        if opens_at and closes_at and closes_at < opens_at:
            raise serializers.ValidationError({
                "closes_at": "La clôture doit être postérieure à l'ouverture."
            })
        return attrs


class FundingUpdateSerializer(FundingCreateSerializer):
    title = serializers.CharField(max_length=220, required=False)
    space_id = serializers.UUIDField(read_only=True)
    currency = serializers.CharField(max_length=3, required=False)
    status = serializers.ChoiceField(choices=ActivityStatus.choices, required=False)
    visibility = serializers.ChoiceField(choices=ActivityVisibility.choices, required=False)


class FundingContributionSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0.01)
    client_reference = serializers.CharField(max_length=120, required=False, allow_blank=True)
