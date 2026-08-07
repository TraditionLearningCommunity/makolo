from rest_framework import serializers

from events.models import Event

from tickets.models import Ticket, TicketOrder, TicketOrderItem, TicketType
from tickets.services import create_order


class EventSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = ["id", "title", "slug", "start_at", "end_at", "status"]
        read_only_fields = fields


class TicketTypeSerializer(serializers.ModelSerializer):
    event = EventSummarySerializer(read_only=True)
    event_id = serializers.PrimaryKeyRelatedField(
        source="event",
        queryset=Event.objects.all(),
        write_only=True,
    )
    is_free = serializers.BooleanField(read_only=True)
    available_quantity = serializers.IntegerField(read_only=True, allow_null=True)
    is_on_sale = serializers.BooleanField(read_only=True)

    class Meta:
        model = TicketType
        fields = [
            "id",
            "event",
            "event_id",
            "name",
            "slug",
            "description",
            "price",
            "currency",
            "quantity_total",
            "reserved_quantity",
            "issued_quantity",
            "available_quantity",
            "sales_start_at",
            "sales_end_at",
            "min_per_order",
            "max_per_order",
            "is_active",
            "is_free",
            "is_on_sale",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "slug",
            "reserved_quantity",
            "issued_quantity",
            "available_quantity",
            "is_free",
            "is_on_sale",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        instance = self.instance
        event = attrs.get("event", getattr(instance, "event", None))
        request = self.context.get("request")
        if event and request and not request.user.is_staff:
            if event.organizer_id != request.user.pk:
                raise serializers.ValidationError(
                    {"event_id": "Vous ne pouvez gérer que vos propres événements."}
                )
        return attrs


class TicketOrderItemSerializer(serializers.ModelSerializer):
    ticket_type = TicketTypeSerializer(read_only=True)
    line_total = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        read_only=True,
    )

    class Meta:
        model = TicketOrderItem
        fields = ["id", "ticket_type", "quantity", "unit_price", "line_total"]
        read_only_fields = fields


class TicketSerializer(serializers.ModelSerializer):
    event = EventSummarySerializer(read_only=True)
    ticket_type = TicketTypeSerializer(read_only=True)
    order_reference = serializers.CharField(source="order.reference", read_only=True)
    qr_token = serializers.CharField(read_only=True)
    is_valid = serializers.BooleanField(read_only=True)

    class Meta:
        model = Ticket
        fields = [
            "id",
            "code",
            "event",
            "ticket_type",
            "order_reference",
            "holder_name",
            "holder_email",
            "status",
            "issued_at",
            "used_at",
            "cancelled_at",
            "qr_token",
            "is_valid",
        ]
        read_only_fields = fields


class TicketOrderSerializer(serializers.ModelSerializer):
    event = EventSummarySerializer(read_only=True)
    items = TicketOrderItemSerializer(many=True, read_only=True)
    tickets = TicketSerializer(many=True, read_only=True)

    class Meta:
        model = TicketOrder
        fields = [
            "id",
            "reference",
            "event",
            "customer_name",
            "customer_email",
            "status",
            "total_amount",
            "currency",
            "expires_at",
            "confirmed_at",
            "cancelled_at",
            "items",
            "tickets",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class TicketSelectionSerializer(serializers.Serializer):
    ticket_type_id = serializers.PrimaryKeyRelatedField(
        source="ticket_type",
        queryset=TicketType.objects.select_related("event").all(),
    )
    quantity = serializers.IntegerField(min_value=1)


class TicketOrderCreateSerializer(serializers.Serializer):
    event_id = serializers.PrimaryKeyRelatedField(
        source="event",
        queryset=Event.objects.all(),
    )
    customer_name = serializers.CharField(max_length=180)
    customer_email = serializers.EmailField()
    items = TicketSelectionSerializer(many=True, allow_empty=False)

    def validate(self, attrs):
        event = attrs["event"]
        seen = set()
        for item in attrs["items"]:
            ticket_type = item["ticket_type"]
            if ticket_type.event_id != event.pk:
                raise serializers.ValidationError(
                    {"items": "Tous les types de billets doivent appartenir à l’événement."}
                )
            if ticket_type.pk in seen:
                raise serializers.ValidationError(
                    {"items": "Un type de billet ne peut apparaître qu’une fois."}
                )
            seen.add(ticket_type.pk)
        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        selections = [
            (item["ticket_type"], item["quantity"])
            for item in validated_data.pop("items")
        ]
        return create_order(
            buyer=request.user,
            selections=selections,
            **validated_data,
        )
