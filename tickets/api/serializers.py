from rest_framework import serializers

from crm.services import attribute_order_from_campaign, resolve_campaign_recipient_token
from events.models import Event
from events.permissions import user_can_manage_event
from events.selectors import get_events_visible_to
from partners.services import attribute_order

from tickets.models import (
    Ticket,
    TicketOrder,
    TicketOrderItem,
    TicketTransfer,
    TicketType,
    TicketWaitlistEntry,
)
from tickets.services import create_order, create_ticket_transfer, join_waitlist


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
            "id", "event", "event_id", "name", "slug", "description", "price", "currency",
            "quantity_total", "reserved_quantity", "issued_quantity", "available_quantity",
            "sales_start_at", "sales_end_at", "min_per_order", "max_per_order", "is_active",
            "is_free", "is_on_sale", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "slug", "reserved_quantity", "issued_quantity", "available_quantity", "is_free",
            "is_on_sale", "created_at", "updated_at",
        ]

    def validate(self, attrs):
        instance = self.instance
        event = attrs.get("event", getattr(instance, "event", None))
        request = self.context.get("request")
        if event and request and not user_can_manage_event(request.user, event):
            raise serializers.ValidationError({"event_id": "Vous ne pouvez pas gérer les billets de cet événement."})
        return attrs


class TicketOrderItemSerializer(serializers.ModelSerializer):
    ticket_type = TicketTypeSerializer(read_only=True)
    line_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

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
            "id", "code", "event", "ticket_type", "order_reference", "holder_name", "holder_email",
            "status", "issued_at", "used_at", "cancelled_at", "qr_token", "is_valid",
        ]
        read_only_fields = fields


class TicketOrderSerializer(serializers.ModelSerializer):
    event = EventSummarySerializer(read_only=True)
    items = TicketOrderItemSerializer(many=True, read_only=True)
    tickets = TicketSerializer(many=True, read_only=True)

    class Meta:
        model = TicketOrder
        fields = [
            "id", "reference", "event", "customer_name", "customer_email", "status", "total_amount",
            "currency", "expires_at", "confirmed_at", "cancelled_at", "items", "tickets", "created_at", "updated_at",
        ]
        read_only_fields = fields


class TicketSelectionSerializer(serializers.Serializer):
    ticket_type_id = serializers.PrimaryKeyRelatedField(
        source="ticket_type",
        queryset=TicketType.objects.select_related("event").all(),
    )
    quantity = serializers.IntegerField(min_value=1)


class TicketOrderCreateSerializer(serializers.Serializer):
    event_id = serializers.PrimaryKeyRelatedField(source="event", queryset=Event.objects.all())
    customer_name = serializers.CharField(max_length=180)
    customer_email = serializers.EmailField()
    referral_code = serializers.CharField(max_length=40, required=False, allow_blank=True, write_only=True)
    campaign_token = serializers.CharField(max_length=600, required=False, allow_blank=True, write_only=True)
    items = TicketSelectionSerializer(many=True, allow_empty=False)

    def validate(self, attrs):
        event = attrs["event"]
        request = self.context["request"]
        if not get_events_visible_to(request.user, for_detail=True).filter(pk=event.pk).exists():
            raise serializers.ValidationError({"event_id": "Cet événement n’est pas accessible pour une commande."})

        seen = set()
        for item in attrs["items"]:
            ticket_type = item["ticket_type"]
            if ticket_type.event_id != event.pk:
                raise serializers.ValidationError({"items": "Tous les types de billets doivent appartenir à l’événement."})
            if ticket_type.pk in seen:
                raise serializers.ValidationError({"items": "Un type de billet ne peut apparaître qu’une fois."})
            seen.add(ticket_type.pk)

        token = attrs.get("campaign_token", "")
        if token:
            try:
                recipient = resolve_campaign_recipient_token(token)
            except Exception as exc:
                from django.core.exceptions import ValidationError as DjangoValidationError

                if isinstance(exc, DjangoValidationError):
                    raise serializers.ValidationError({"campaign_token": exc.messages}) from exc
                raise
            campaign = recipient.campaign
            if campaign.organization_id != event.organization_id or (campaign.event_id and campaign.event_id != event.pk):
                raise serializers.ValidationError({"campaign_token": "Cette campagne ne peut pas attribuer une vente pour cet événement."})
            attrs["_campaign_recipient"] = recipient
        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        referral_code = validated_data.pop("referral_code", "")
        validated_data.pop("campaign_token", "")
        campaign_recipient = validated_data.pop("_campaign_recipient", None)
        selections = [(item["ticket_type"], item["quantity"]) for item in validated_data.pop("items")]
        order = create_order(buyer=request.user, selections=selections, **validated_data)
        attribute_order(order=order, referral_code=referral_code or None)
        attribute_order_from_campaign(order=order, request=request, recipient=campaign_recipient)
        return order


class TicketWaitlistSerializer(serializers.ModelSerializer):
    ticket_type = TicketTypeSerializer(read_only=True)
    offered_order = TicketOrderSerializer(read_only=True)
    is_offer_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = TicketWaitlistEntry
        fields = [
            "id", "ticket_type", "requested_quantity", "status", "offered_order", "offered_at", "offer_expires_at",
            "converted_at", "cancelled_at", "is_offer_active", "created_at", "updated_at",
        ]
        read_only_fields = fields


class TicketWaitlistCreateSerializer(serializers.Serializer):
    ticket_type_id = serializers.PrimaryKeyRelatedField(
        source="ticket_type", queryset=TicketType.objects.select_related("event").all()
    )
    quantity = serializers.IntegerField(min_value=1, default=1)

    def create(self, validated_data):
        return join_waitlist(
            user=self.context["request"].user,
            ticket_type=validated_data["ticket_type"],
            quantity=validated_data["quantity"],
        )


class TicketTransferSerializer(serializers.ModelSerializer):
    ticket = TicketSerializer(read_only=True)
    sender_name = serializers.CharField(source="sender.full_name", read_only=True)
    sender_username = serializers.CharField(source="sender.username", read_only=True)
    recipient_name = serializers.CharField(source="recipient.full_name", read_only=True)
    recipient_username = serializers.CharField(source="recipient.username", read_only=True)
    is_pending_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = TicketTransfer
        fields = [
            "id", "ticket", "sender_name", "sender_username", "recipient_name", "recipient_username",
            "recipient_email", "status", "expires_at", "accepted_at", "declined_at", "cancelled_at",
            "expired_at", "is_pending_active", "created_at", "updated_at",
        ]
        read_only_fields = fields


class TicketTransferCreateSerializer(serializers.Serializer):
    ticket_id = serializers.PrimaryKeyRelatedField(
        source="ticket", queryset=Ticket.objects.select_related("event", "owner").all()
    )
    recipient_email = serializers.EmailField()

    def create(self, validated_data):
        return create_ticket_transfer(
            ticket=validated_data["ticket"],
            sender=self.context["request"].user,
            recipient_email=validated_data["recipient_email"],
        )
