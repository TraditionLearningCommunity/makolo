from django.core.exceptions import ValidationError as DjangoValidationError

from rest_framework import serializers

from events.models import Event, EventCategory, EventVenue, EventVisibility
from events.validators import validate_event_cover
from organizations.models import Organization
from organizations.permissions import user_can_create_events_for_organization


class EventCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = EventCategory
        fields = ["id", "name", "slug", "description"]
        read_only_fields = fields


class EventVenueSerializer(serializers.ModelSerializer):
    address = serializers.CharField(source="effective_address", read_only=True)
    city = serializers.CharField(source="effective_city", read_only=True)
    country = serializers.CharField(source="effective_country", read_only=True)
    latitude = serializers.DecimalField(source="effective_latitude", max_digits=9, decimal_places=6, read_only=True)
    longitude = serializers.DecimalField(source="effective_longitude", max_digits=9, decimal_places=6, read_only=True)

    class Meta:
        model = EventVenue
        fields = ["id", "name", "kind", "address", "city", "country", "latitude", "longitude", "online_url"]
        read_only_fields = fields


class OrganizerSummarySerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    username = serializers.CharField(read_only=True)
    full_name = serializers.CharField(read_only=True)


class OrganizationSummarySerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    name = serializers.CharField(read_only=True)
    slug = serializers.CharField(read_only=True)
    verification_status = serializers.CharField(read_only=True)


class EventListSerializer(serializers.ModelSerializer):
    title = serializers.CharField(read_only=True)
    short_description = serializers.CharField(read_only=True)
    status = serializers.CharField(read_only=True)
    visibility = serializers.CharField(read_only=True)
    start_at = serializers.DateTimeField(read_only=True)
    end_at = serializers.DateTimeField(read_only=True)
    capacity = serializers.IntegerField(read_only=True, allow_null=True)
    category = EventCategorySerializer(read_only=True)
    venue = EventVenueSerializer(read_only=True)
    organizer = OrganizerSummarySerializer(read_only=True)
    organization = OrganizationSummarySerializer(read_only=True)
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
            "organization",
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
        return request.build_absolute_uri(obj.cover_image.url) if request else obj.cover_image.url


class EventDetailSerializer(EventListSerializer):
    description = serializers.CharField(read_only=True)
    timezone = serializers.CharField(read_only=True)

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


class EventWriteSerializer(serializers.Serializer):
    """Stable Event API vocabulary, routed to canonical services by the view."""

    organization_id = serializers.PrimaryKeyRelatedField(
        source="organization",
        queryset=Organization.objects.all(),
        required=False,
    )
    title = serializers.CharField(max_length=220, required=False)
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
    short_description = serializers.CharField(max_length=320, allow_blank=True, required=False)
    description = serializers.CharField(allow_blank=True, required=False)
    cover_image = serializers.ImageField(allow_null=True, required=False)
    visibility = serializers.ChoiceField(choices=EventVisibility.choices, required=False)
    start_at = serializers.DateTimeField(required=False)
    end_at = serializers.DateTimeField(required=False)
    registration_start_at = serializers.DateTimeField(allow_null=True, required=False)
    registration_end_at = serializers.DateTimeField(allow_null=True, required=False)
    timezone = serializers.CharField(max_length=100, required=False)
    # Compatibility input/output: backed by a canonical Event-scoped CapacityPool.
    capacity = serializers.IntegerField(min_value=1, allow_null=True, required=False)

    def validate_cover_image(self, value):
        if value is None:
            return value
        try:
            validate_event_cover(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc
        return value

    def validate(self, attrs):
        instance = self.instance
        organization = attrs.get("organization", getattr(instance, "organization", None))
        request = self.context.get("request")
        if request and organization and not user_can_create_events_for_organization(request.user, organization):
            raise serializers.ValidationError(
                {"organization_id": "Vous n'avez pas le droit de gérer les événements de cette organisation."}
            )

        title = attrs.get("title", getattr(instance, "title", None))
        start_at = attrs.get("start_at", getattr(instance, "start_at", None))
        end_at = attrs.get("end_at", getattr(instance, "end_at", None))
        if instance is None:
            required = {}
            if not title:
                required["title"] = "Ce champ est obligatoire."
            if not start_at:
                required["start_at"] = "Ce champ est obligatoire."
            if not end_at:
                required["end_at"] = "Ce champ est obligatoire."
            if required:
                raise serializers.ValidationError(required)

        registration_start_at = attrs.get(
            "registration_start_at", getattr(instance, "registration_start_at", None)
        )
        registration_end_at = attrs.get(
            "registration_end_at", getattr(instance, "registration_end_at", None)
        )
        errors = {}
        if start_at and end_at and end_at <= start_at:
            errors["end_at"] = "La fin doit être postérieure au début."
        if registration_start_at and registration_end_at and registration_end_at <= registration_start_at:
            errors["registration_end_at"] = "La fin des inscriptions doit être postérieure à leur début."
        if registration_end_at and end_at and registration_end_at > end_at:
            errors["registration_end_at"] = "Les inscriptions ne peuvent pas se terminer après l’événement."
        if registration_start_at and end_at and registration_start_at >= end_at:
            errors["registration_start_at"] = "Les inscriptions doivent commencer avant la fin de l’événement."
        if errors:
            raise serializers.ValidationError(errors)
        return attrs

    def to_representation(self, instance):
        request = self.context.get("request")
        return EventDetailSerializer(instance, context={"request": request}).data
