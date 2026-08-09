from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from crm.models import CommunicationCampaign
from events.models import Event
from growth.models import EventFeedback, MarketingLink
from growth.permissions import user_can_manage_growth_acquisition
from growth.services import submit_event_feedback
from organizations.models import Organization


class MarketingLinkSerializer(serializers.ModelSerializer):
    short_path = serializers.SerializerMethodField()
    visits = serializers.IntegerField(source="visits.count", read_only=True)
    conversions = serializers.SerializerMethodField()

    class Meta:
        model = MarketingLink
        fields = [
            "id",
            "organization",
            "event",
            "crm_campaign",
            "name",
            "channel",
            "code",
            "short_path",
            "attribution_window_days",
            "is_active",
            "visits",
            "conversions",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "code", "short_path", "visits", "conversions", "created_at", "updated_at"]

    def get_short_path(self, obj):
        return f"/g/{obj.code}/"

    def get_conversions(self, obj):
        return obj.attributions.filter(status="confirmed").count()

    def validate(self, attrs):
        request = self.context["request"]
        organization = attrs.get("organization", getattr(self.instance, "organization", None))
        event = attrs.get("event", getattr(self.instance, "event", None))
        campaign = attrs.get("crm_campaign", getattr(self.instance, "crm_campaign", None))
        if not organization or not user_can_manage_growth_acquisition(request.user, organization):
            raise serializers.ValidationError({"organization": "Un rôle Owner, Admin ou Marketing est requis."})
        if event and event.organization_id != organization.pk:
            raise serializers.ValidationError({"event": "L'événement appartient à une autre organisation."})
        if campaign and campaign.organization_id != organization.pk:
            raise serializers.ValidationError({"crm_campaign": "La campagne appartient à une autre organisation."})
        candidate = MarketingLink(
            organization=organization,
            event=event,
            crm_campaign=campaign,
            name=attrs.get("name", getattr(self.instance, "name", "")),
            channel=attrs.get("channel", getattr(self.instance, "channel", "")),
            attribution_window_days=attrs.get(
                "attribution_window_days",
                getattr(self.instance, "attribution_window_days", 30),
            ),
            created_by=request.user,
        )
        try:
            candidate.full_clean(exclude=["code"])
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict) from exc
        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        link = MarketingLink(created_by=request.user, **validated_data)
        link.full_clean(exclude=["code"])
        link.save()
        return link


class EventFeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventFeedback
        fields = ["id", "event", "rating", "comment", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

    def create(self, validated_data):
        request = self.context["request"]
        return submit_event_feedback(user=request.user, **validated_data)
