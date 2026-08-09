from rest_framework import serializers

from crm.models import AudienceKind, CommunicationKind, MarketingConsent


class CRMContactSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    organization_id = serializers.UUIDField(read_only=True)
    user_id = serializers.UUIDField(read_only=True, allow_null=True)
    email = serializers.EmailField(read_only=True)
    name = serializers.CharField(read_only=True)
    phone = serializers.CharField(read_only=True)
    source = serializers.CharField(read_only=True)
    marketing_consent = serializers.ChoiceField(choices=MarketingConsent.choices, read_only=True)
    consent_source = serializers.CharField(read_only=True)
    first_seen_at = serializers.DateTimeField(read_only=True)
    last_seen_at = serializers.DateTimeField(read_only=True)


class AudienceSegmentSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    organization_id = serializers.UUIDField(read_only=True)
    event_id = serializers.UUIDField(read_only=True, allow_null=True)
    ticket_type_id = serializers.UUIDField(read_only=True, allow_null=True)
    name = serializers.CharField(read_only=True)
    description = serializers.CharField(read_only=True)
    audience_kind = serializers.ChoiceField(choices=AudienceKind.choices, read_only=True)
    marketing_consent_only = serializers.BooleanField(read_only=True)
    city = serializers.CharField(read_only=True)
    country = serializers.CharField(read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)


class AudienceSegmentCreateSerializer(serializers.Serializer):
    organization_id = serializers.UUIDField()
    name = serializers.CharField(max_length=160)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    event_id = serializers.UUIDField(required=False, allow_null=True)
    ticket_type_id = serializers.UUIDField(required=False, allow_null=True)
    audience_kind = serializers.ChoiceField(choices=AudienceKind.choices, default=AudienceKind.ALL)
    marketing_consent_only = serializers.BooleanField(default=False)
    city = serializers.CharField(required=False, allow_blank=True, max_length=120, default="")
    country = serializers.CharField(required=False, allow_blank=True, max_length=120, default="")
    is_active = serializers.BooleanField(default=True)


class CommunicationCampaignSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    organization_id = serializers.UUIDField(read_only=True)
    segment_id = serializers.UUIDField(read_only=True)
    event_id = serializers.UUIDField(read_only=True, allow_null=True)
    name = serializers.CharField(read_only=True)
    kind = serializers.ChoiceField(choices=CommunicationKind.choices, read_only=True)
    subject = serializers.CharField(read_only=True)
    preview_text = serializers.CharField(read_only=True)
    body = serializers.CharField(read_only=True)
    cta_label = serializers.CharField(read_only=True)
    cta_url = serializers.URLField(read_only=True)
    status = serializers.CharField(read_only=True)
    scheduled_at = serializers.DateTimeField(read_only=True, allow_null=True)
    started_at = serializers.DateTimeField(read_only=True, allow_null=True)
    completed_at = serializers.DateTimeField(read_only=True, allow_null=True)
    created_at = serializers.DateTimeField(read_only=True)


class CommunicationCampaignCreateSerializer(serializers.Serializer):
    organization_id = serializers.UUIDField()
    segment_id = serializers.UUIDField()
    event_id = serializers.UUIDField(required=False, allow_null=True)
    name = serializers.CharField(max_length=160)
    kind = serializers.ChoiceField(choices=CommunicationKind.choices, default=CommunicationKind.MARKETING)
    subject = serializers.CharField(max_length=180)
    preview_text = serializers.CharField(required=False, allow_blank=True, max_length=220, default="")
    body = serializers.CharField()
    cta_label = serializers.CharField(required=False, allow_blank=True, max_length=80, default="")
    cta_url = serializers.URLField(required=False, allow_blank=True, default="")
    scheduled_at = serializers.DateTimeField(required=False, allow_null=True)


class ConsentUpdateSerializer(serializers.Serializer):
    subscribed = serializers.BooleanField()
    source = serializers.CharField(required=False, allow_blank=True, max_length=120, default="")

    def validate(self, attrs):
        if attrs["subscribed"] and not attrs.get("source", "").strip():
            raise serializers.ValidationError({"source": "Une source de consentement est requise pour abonner un contact."})
        return attrs
