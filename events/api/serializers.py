from django.core.exceptions import ValidationError as DjangoValidationError

from rest_framework import serializers

from events.models import Event, EventCategory, EventVenue
from events.validators import validate_event_cover


class EventCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = EventCategory
        fields = ["id", "name", "slug", "description"]
        read_only_fields = fields


class EventVenueSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventVenue
        fields = [
            "id",
            "name",
            "kind",
            "address",
            "city",
            "country",
            "latitude",
            "longitude",
            "online_url",
        ]
        read_only_fields = fields


class OrganizerSummarySerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    username = serializers.CharField(read_only=True)
    full_name = serializers.CharField(read_only=True)


class EventListSerializer(serializers.ModelSerializer):
    category = EventCategorySerializer(read_only=True)
    venue = EventVenueSerializer(read_only=True)
    organizer = OrganizerSummarySerializer(read_only=True)
    cover_image_url = serializers.SerializerMethodField()
    is_registration_open = serializers.BooleanField(read_only=True)

    class Meta:
        model = Event
        fields = [
            "id",
            "title",
            "slug",
            "short_description",
            "category",
            "venue",
            "organizer",
            "status",
            "visibility",
            "start_at",
            "end_at",
            "capacity",
            "cover_image_url",
            "is_registration_open",
        ]
        read_only_fields = fields

    def get_cover_image_url(self, obj):
        if not obj.cover_image:
            return None
        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(obj.cover_image.url)
        return obj.cover_image.url


class EventDetailSerializer(EventListSerializer):
    class Meta(EventListSerializer.Meta):
        fields = EventListSerializer.Meta.fields + [
            "description",
            "registration_start_at",
            "registration_end_at",
            "timezone",
            "published_at",
            "cancelled_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class EventWriteSerializer(serializers.ModelSerializer):
    category_id = serializers.PrimaryKeyRelatedField(
        source="category",
        queryset=EventCategory.objects.filter(is_active=True),
        allow_null=True,
        required=False,
    )
    venue_id = serializers.PrimaryKeyRelatedField(
        source="venue",
        queryset=EventVenue.objects.filter(is_active=True),
        allow_null=True,
        required=False,
    )

    class Meta:
        model = Event
        fields = [
            "title",
            "category_id",
            "venue_id",
            "short_description",
            "description",
            "cover_image",
            "visibility",
            "start_at",
            "end_at",
            "registration_start_at",
            "registration_end_at",
            "timezone",
            "capacity",
        ]

    def validate_cover_image(self, value):
        try:
            validate_event_cover(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc
        return value

    def validate(self, attrs):
        instance = self.instance
        start_at = attrs.get("start_at", getattr(instance, "start_at", None))
        end_at = attrs.get("end_at", getattr(instance, "end_at", None))
        registration_start_at = attrs.get(
            "registration_start_at",
            getattr(instance, "registration_start_at", None),
        )
        registration_end_at = attrs.get(
            "registration_end_at",
            getattr(instance, "registration_end_at", None),
        )

        errors = {}
        if start_at and end_at and end_at <= start_at:
            errors["end_at"] = "La fin doit être postérieure au début."

        if (
            registration_start_at
            and registration_end_at
            and registration_end_at <= registration_start_at
        ):
            errors["registration_end_at"] = (
                "La fin des inscriptions doit être postérieure à leur début."
            )

        if registration_end_at and end_at and registration_end_at > end_at:
            errors["registration_end_at"] = (
                "Les inscriptions ne peuvent pas se terminer après l’événement."
            )

        if registration_start_at and end_at and registration_start_at >= end_at:
            errors["registration_start_at"] = (
                "Les inscriptions doivent commencer avant la fin de l’événement."
            )

        if errors:
            raise serializers.ValidationError(errors)
        return attrs
