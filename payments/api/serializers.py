from rest_framework import serializers

from tickets.models import TicketOrder

from payments.models import Payment, PaymentEvent, PaymentMethod, PaymentProvider, Refund
from payments.services import initiate_payment


class PaymentOrderSerializer(serializers.ModelSerializer):
    event_title = serializers.CharField(source="event.title", read_only=True)
    event_slug = serializers.CharField(source="event.slug", read_only=True)

    class Meta:
        model = TicketOrder
        fields = [
            "id", "reference", "event_title", "event_slug", "status", "total_amount",
            "currency", "expires_at", "confirmed_at",
        ]
        read_only_fields = fields


class RefundSerializer(serializers.ModelSerializer):
    class Meta:
        model = Refund
        fields = [
            "id", "reference", "status", "amount", "currency", "reason",
            "provider_reference", "processed_at", "created_at",
        ]
        read_only_fields = fields


class PaymentSerializer(serializers.ModelSerializer):
    order = PaymentOrderSerializer(read_only=True)
    refunds = RefundSerializer(many=True, read_only=True)
    refunded_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    refundable_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = Payment
        fields = [
            "id", "reference", "order", "provider", "method", "status", "amount",
            "currency", "payer_name", "payer_email", "payer_phone", "provider_reference",
            "checkout_url", "failure_code", "failure_message", "refunded_amount",
            "refundable_amount", "refunds", "processed_at", "succeeded_at", "failed_at",
            "cancelled_at", "created_at", "updated_at",
        ]
        read_only_fields = fields


class PaymentCreateSerializer(serializers.Serializer):
    order_id = serializers.PrimaryKeyRelatedField(
        source="order",
        queryset=TicketOrder.objects.select_related("event", "buyer").all(),
    )
    provider = serializers.ChoiceField(choices=PaymentProvider.choices)
    method = serializers.ChoiceField(choices=PaymentMethod.choices)
    payer_name = serializers.CharField(max_length=180, required=False, allow_blank=True)
    payer_email = serializers.EmailField(required=False, allow_blank=True)
    payer_phone = serializers.CharField(max_length=40, required=False, allow_blank=True)
    idempotency_key = serializers.CharField(max_length=128, required=False, allow_blank=True)

    def validate(self, attrs):
        key = (attrs.get("idempotency_key") or "").strip()
        if not key:
            return attrs
        existing = Payment.objects.filter(idempotency_key=key).first()
        if not existing:
            return attrs
        if (
            existing.order_id != attrs["order"].pk
            or existing.provider != attrs["provider"]
            or existing.method != attrs["method"]
        ):
            raise serializers.ValidationError(
                {"idempotency_key": "Cette clé d’idempotence appartient à une autre tentative de paiement."}
            )
        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        requested_provider = validated_data["provider"]
        requested_method = validated_data["method"]
        payment = initiate_payment(
            actor=request.user,
            idempotency_key=validated_data.pop("idempotency_key", "") or None,
            **validated_data,
        )
        if payment.provider != requested_provider or payment.method != requested_method:
            raise serializers.ValidationError(
                {"idempotency_key": "Cette clé d’idempotence appartient à une autre tentative de paiement."}
            )
        return payment


class ManualCompleteSerializer(serializers.Serializer):
    provider_reference = serializers.CharField(max_length=160, required=False, allow_blank=True)


class RefundRequestSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True)
    idempotency_key = serializers.CharField(max_length=128, required=False, allow_blank=True)


class PaymentEventSerializer(serializers.ModelSerializer):
    payment_reference = serializers.CharField(source="payment.reference", read_only=True, allow_null=True)

    class Meta:
        model = PaymentEvent
        fields = [
            "id", "payment_reference", "provider", "event_id", "event_type",
            "signature_valid", "processed", "payload_hash", "processing_error",
            "received_at", "processed_at",
        ]
        read_only_fields = fields
