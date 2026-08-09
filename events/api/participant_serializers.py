from rest_framework import serializers

from events.models import Event, EventCategory, EventVenue
from organizations.models import Organization, OrganizationVerificationStatus
from tickets.models import TicketType


class ParticipantEventCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = EventCategory
        fields = ["id", "name", "slug"]
        read_only_fields = fields


class ParticipantVenueSerializer(serializers.ModelSerializer):
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
        ]
        read_only_fields = fields


class ParticipantOrganizationSerializer(serializers.ModelSerializer):
    is_verified = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = ["id", "name", "slug", "is_verified"]
        read_only_fields = fields

    def get_is_verified(self, obj):
        return obj.verification_status == OrganizationVerificationStatus.VERIFIED


class ParticipantEventBaseSerializer(serializers.ModelSerializer):
    category = ParticipantEventCategorySerializer(read_only=True)
    venue = ParticipantVenueSerializer(read_only=True)
    organization = ParticipantOrganizationSerializer(read_only=True)
    image_url = serializers.SerializerMethodField()
    registration_status = serializers.SerializerMethodField()
    ticket_availability = serializers.SerializerMethodField()

    def get_image_url(self, obj):
        if not obj.cover_image:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(obj.cover_image.url) if request else obj.cover_image.url

    def get_registration_status(self, obj):
        from django.utils import timezone

        now = timezone.now()
        if obj.registration_start_at and now < obj.registration_start_at:
            return "not_started"
        if now >= obj.end_at:
            return "event_ended"
        if obj.registration_end_at and now > obj.registration_end_at:
            return "closed"
        return "open" if obj.is_registration_open else "closed"

    def get_ticket_availability(self, obj):
        ticket_types = [
            item
            for item in obj.ticket_types.all()
            if item.is_active and item.is_public
        ]
        on_sale = [item for item in ticket_types if item.is_on_sale]
        stock_remaining = any(
            item.available_quantity is None or item.available_quantity > 0
            for item in ticket_types
        )
        return {
            "registration_open": obj.is_registration_open,
            "has_public_ticket_types": bool(ticket_types),
            "has_tickets_on_sale": bool(on_sale),
            "can_purchase": bool(on_sale),
            "sold_out": bool(ticket_types) and not stock_remaining,
        }


class ParticipantEventListSerializer(ParticipantEventBaseSerializer):
    class Meta:
        model = Event
        fields = [
            "id",
            "slug",
            "title",
            "short_description",
            "image_url",
            "category",
            "start_at",
            "end_at",
            "timezone",
            "registration_status",
            "venue",
            "organization",
            "ticket_availability",
        ]
        read_only_fields = fields


class ParticipantEventDetailSerializer(ParticipantEventBaseSerializer):
    class Meta:
        model = Event
        fields = [
            "id",
            "slug",
            "title",
            "short_description",
            "description",
            "image_url",
            "category",
            "start_at",
            "end_at",
            "registration_start_at",
            "registration_end_at",
            "timezone",
            "registration_status",
            "venue",
            "organization",
            "ticket_availability",
        ]
        read_only_fields = fields


class ParticipantTicketTypeSerializer(serializers.ModelSerializer):
    is_free = serializers.BooleanField(read_only=True)
    available_quantity = serializers.IntegerField(read_only=True, allow_null=True)
    is_on_sale = serializers.BooleanField(read_only=True)

    class Meta:
        model = TicketType
        fields = [
            "id",
            "name",
            "description",
            "price",
            "currency",
            "is_free",
            "available_quantity",
            "min_per_order",
            "max_per_order",
            "sales_start_at",
            "sales_end_at",
            "is_on_sale",
        ]
        read_only_fields = fields


class DiscoverEventQuerySerializer(serializers.Serializer):
    search = serializers.CharField(required=False, allow_blank=True, max_length=120)
    category = serializers.SlugField(required=False, allow_blank=True, max_length=140)
    city = serializers.CharField(required=False, allow_blank=True, max_length=120)
    date_min = serializers.DateField(required=False)
    date_max = serializers.DateField(required=False)
    ordering = serializers.ChoiceField(
        choices=["start_at", "-start_at"],
        required=False,
        default="start_at",
    )

    def validate(self, attrs):
        date_min = attrs.get("date_min")
        date_max = attrs.get("date_max")
        if date_min and date_max and date_max < date_min:
            raise serializers.ValidationError(
                {"date_max": "La date maximum doit être postérieure ou égale à la date minimum."}
            )
        return attrs
