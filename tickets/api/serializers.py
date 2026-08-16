import hashlib
import json
from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError

from rest_framework import serializers

from crm.services import attribute_order_from_campaign, resolve_campaign_recipient_token
from events.models import Event
from events.permissions import user_can_manage_event
from events.selectors import get_events_available_for_ticket_purchase
from partners.services import attribute_order
from tickets.models import (
    Ticket,
    TicketOrder,
    TicketOrderItem,
    TicketTransfer,
    TicketType,
    TicketWaitlistEntry,
)
from tickets.order_idempotency import create_idempotent_order_with_promotion, get_idempotent_order
from tickets.services import configure_ticket_type, create_ticket_transfer, join_waitlist


class EventSummarySerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    title = serializers.CharField(read_only=True)
    slug = serializers.CharField(read_only=True)
    start_at = serializers.DateTimeField(read_only=True)
    end_at = serializers.DateTimeField(read_only=True, allow_null=True)
    status = serializers.CharField(read_only=True)


class TicketTypeSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    event = EventSummarySerializer(read_only=True)
    event_id = serializers.PrimaryKeyRelatedField(source="event", queryset=Event.objects.all(), write_only=True)
    name = serializers.CharField(max_length=140)
    slug = serializers.CharField(read_only=True)
    description = serializers.CharField(required=False, allow_blank=True)
    price = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0)
    currency = serializers.CharField(max_length=3, default="USD")
    quantity_total = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    reserved_quantity = serializers.IntegerField(read_only=True)
    issued_quantity = serializers.IntegerField(read_only=True)
    available_quantity = serializers.IntegerField(read_only=True, allow_null=True)
    sales_start_at = serializers.DateTimeField(required=False, allow_null=True)
    sales_end_at = serializers.DateTimeField(required=False, allow_null=True)
    min_per_order = serializers.IntegerField(min_value=1, default=1)
    max_per_order = serializers.IntegerField(min_value=1, default=10)
    is_active = serializers.BooleanField(default=True)
    is_public = serializers.BooleanField(default=True)
    is_free = serializers.BooleanField(read_only=True)
    is_on_sale = serializers.BooleanField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)

    def validate_currency(self, value):
        return (value or "USD").upper()

    def validate(self, attrs):
        instance = self.instance
        event = attrs.get("event", getattr(instance, "event", None))
        request = self.context.get("request")
        if event and request and not user_can_manage_event(request.user, event):
            raise serializers.ValidationError({"event_id": "Vous ne pouvez pas gérer les billets de cet événement."})
        if instance is not None and event and instance.event_id != event.pk:
            raise serializers.ValidationError({"event_id": "Un type de billet existant ne peut pas changer d’événement."})
        minimum = attrs.get("min_per_order", getattr(instance, "min_per_order", 1))
        maximum = attrs.get("max_per_order", getattr(instance, "max_per_order", 10))
        if maximum < minimum:
            raise serializers.ValidationError({"max_per_order": "Le maximum doit être supérieur ou égal au minimum."})
        start = attrs.get("sales_start_at", getattr(instance, "sales_start_at", None))
        end = attrs.get("sales_end_at", getattr(instance, "sales_end_at", None))
        if start and end and end <= start:
            raise serializers.ValidationError({"sales_end_at": "La fin des ventes doit être postérieure au début."})
        return attrs

    def _values(self, validated_data):
        instance = self.instance
        defaults = {
            "event": getattr(instance, "event", None),
            "name": getattr(instance, "name", ""),
            "description": getattr(instance, "description", ""),
            "price": getattr(instance, "price", Decimal("0.00")),
            "currency": getattr(instance, "currency", "USD"),
            "quantity_total": getattr(instance, "quantity_total", None),
            "sales_start_at": getattr(instance, "sales_start_at", None),
            "sales_end_at": getattr(instance, "sales_end_at", None),
            "min_per_order": getattr(instance, "min_per_order", 1),
            "max_per_order": getattr(instance, "max_per_order", 10),
            "is_active": getattr(instance, "is_active", True),
            "is_public": getattr(instance, "is_public", True),
        }
        defaults.update(validated_data)
        return defaults

    def create(self, validated_data):
        request = self.context["request"]
        return configure_ticket_type(actor=request.user, **self._values(validated_data))

    def update(self, instance, validated_data):
        request = self.context["request"]
        values = self._values(validated_data)
        return configure_ticket_type(actor=request.user, ticket_type=instance, **values)


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
    holder = serializers.SerializerMethodField()
    qr_token = serializers.CharField(read_only=True)
    is_valid = serializers.BooleanField(read_only=True)
    status = serializers.CharField(source="display_status", read_only=True)

    class Meta:
        model = Ticket
        fields = [
            "id", "code", "event", "ticket_type", "order_reference", "holder",
            "holder_name", "holder_email", "status", "issued_at", "used_at",
            "cancelled_at", "qr_token", "is_valid", "updated_at",
        ]
        read_only_fields = fields

    def get_holder(self, obj):
        access = obj.access if obj.access_id else None
        return {
            "user_id": str(access.beneficiary_id if access else obj.owner_id) if (access or obj.owner_id) else None,
            "name": obj.holder_name,
            "email": obj.holder_email,
        }


class TicketOrderSerializer(serializers.ModelSerializer):
    event = EventSummarySerializer(read_only=True)
    items = TicketOrderItemSerializer(many=True, read_only=True)
    tickets = TicketSerializer(many=True, read_only=True)
    status = serializers.CharField(source="canonical_status", read_only=True)
    total_amount = serializers.DecimalField(source="canonical_total", max_digits=12, decimal_places=2, read_only=True)
    currency = serializers.CharField(source="canonical_currency", read_only=True)
    promotion_code = serializers.SerializerMethodField()
    subtotal_amount = serializers.SerializerMethodField()
    discount_amount = serializers.SerializerMethodField()

    def _redemption(self, obj):
        if obj.commerce_order_id:
            try:
                return obj.commerce_order.promotion_redemption
            except Exception:
                pass
        try:
            return obj.promotion_redemption
        except Exception:
            return None

    def get_promotion_code(self, obj):
        redemption = self._redemption(obj)
        return redemption.code.code if redemption else None

    def get_subtotal_amount(self, obj):
        if obj.commerce_order_id:
            return format(obj.commerce_order.subtotal, ".2f")
        redemption = self._redemption(obj)
        amount = redemption.subtotal_amount if redemption else obj.total_amount
        return format(amount, ".2f")

    def get_discount_amount(self, obj):
        if obj.commerce_order_id:
            return format(obj.commerce_order.discount_total, ".2f")
        redemption = self._redemption(obj)
        amount = redemption.discount_amount if redemption else Decimal("0.00")
        return format(amount, ".2f")

    class Meta:
        model = TicketOrder
        fields = [
            "id", "reference", "idempotency_key", "event", "customer_name", "customer_email", "status",
            "subtotal_amount", "discount_amount", "promotion_code", "total_amount",
            "currency", "expires_at", "confirmed_at", "cancelled_at", "items", "tickets", "created_at", "updated_at",
        ]
        read_only_fields = fields


class TicketSelectionSerializer(serializers.Serializer):
    ticket_type_id = serializers.PrimaryKeyRelatedField(
        source="ticket_type",
        queryset=TicketType.objects.select_related("event__activity", "offer", "capacity_pool").all(),
    )
    quantity = serializers.IntegerField(min_value=1)


class TicketOrderCreateSerializer(serializers.Serializer):
    idempotency_key = serializers.UUIDField(required=False)
    event_id = serializers.PrimaryKeyRelatedField(source="event", queryset=Event.objects.all())
    customer_name = serializers.CharField(max_length=180)
    customer_email = serializers.EmailField()
    referral_code = serializers.CharField(max_length=40, required=False, allow_blank=True, write_only=True)
    campaign_token = serializers.CharField(max_length=600, required=False, allow_blank=True, write_only=True)
    promotion_code = serializers.CharField(max_length=40, required=False, allow_blank=True, write_only=True)
    items = TicketSelectionSerializer(many=True, allow_empty=False)

    def _request_fingerprint(self, attrs):
        request = self.context["request"]
        normalized_items = sorted((str(item["ticket_type"].pk), int(item["quantity"])) for item in attrs["items"])
        payload = {
            "buyer_id": str(request.user.pk),
            "event_id": str(attrs["event"].pk),
            "customer_name": attrs["customer_name"].strip(),
            "customer_email": attrs["customer_email"].strip().lower(),
            "referral_code": attrs.get("referral_code", "").strip(),
            "campaign_token": attrs.get("campaign_token", "").strip(),
            "promotion_code": attrs.get("promotion_code", "").strip().upper(),
            "items": normalized_items,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def validate(self, attrs):
        event = attrs["event"]
        request = self.context["request"]
        fingerprint = self._request_fingerprint(attrs)
        attrs["_idempotency_fingerprint"] = fingerprint
        idempotency_key = attrs.get("idempotency_key")
        if idempotency_key:
            try:
                existing = get_idempotent_order(idempotency_key=idempotency_key, buyer=request.user, fingerprint=fingerprint)
            except DjangoValidationError as exc:
                raise serializers.ValidationError({"idempotency_key": exc.messages}) from exc
            if existing:
                attrs["_existing_order"] = existing
                return attrs

        if not get_events_available_for_ticket_purchase().filter(pk=event.pk).exists():
            raise serializers.ValidationError({"event_id": "Cet événement n’est pas accessible pour une commande."})
        seen = set()
        for item in attrs["items"]:
            ticket_type = item["ticket_type"]
            if ticket_type.event_id != event.pk:
                raise serializers.ValidationError({"items": "Tous les types de billets doivent appartenir à l’événement."})
            if not ticket_type.is_active or not ticket_type.is_public:
                raise serializers.ValidationError({"items": "Un type de billet sélectionné n’est pas disponible au public."})
            if ticket_type.pk in seen:
                raise serializers.ValidationError({"items": "Un type de billet ne peut apparaître qu’une fois."})
            seen.add(ticket_type.pk)

        token = attrs.get("campaign_token", "")
        if token:
            try:
                recipient = resolve_campaign_recipient_token(token)
            except Exception as exc:
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
        existing = validated_data.pop("_existing_order", None)
        if existing:
            return existing
        idempotency_key = validated_data.pop("idempotency_key", None)
        fingerprint = validated_data.pop("_idempotency_fingerprint", "")
        referral_code = validated_data.pop("referral_code", "")
        promotion_code = validated_data.pop("promotion_code", "")
        validated_data.pop("campaign_token", "")
        campaign_recipient = validated_data.pop("_campaign_recipient", None)
        selections = [(item["ticket_type"], item["quantity"]) for item in validated_data.pop("items")]
        order = create_idempotent_order_with_promotion(
            buyer=request.user,
            selections=selections,
            promotion_code=promotion_code,
            idempotency_key=idempotency_key,
            idempotency_fingerprint=fingerprint,
            **validated_data,
        )
        if not getattr(order, "_idempotent_replay", False):
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
        source="ticket_type", queryset=TicketType.objects.select_related("event__activity", "offer", "capacity_pool").all()
    )
    quantity = serializers.IntegerField(min_value=1, default=1)

    def create(self, validated_data):
        return join_waitlist(user=self.context["request"].user, ticket_type=validated_data["ticket_type"], quantity=validated_data["quantity"])


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
    ticket_id = serializers.PrimaryKeyRelatedField(source="ticket", queryset=Ticket.objects.select_related("event__activity", "owner", "access").all())
    recipient_email = serializers.EmailField()

    def create(self, validated_data):
        return create_ticket_transfer(ticket=validated_data["ticket"], sender=self.context["request"].user, recipient_email=validated_data["recipient_email"])
