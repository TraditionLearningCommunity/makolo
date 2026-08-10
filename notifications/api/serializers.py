from rest_framework import serializers

from notifications.models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    is_read = serializers.BooleanField(read_only=True)
    navigation = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            "id",
            "kind",
            "category",
            "title",
            "message",
            "action_url",
            "metadata",
            "navigation",
            "is_read",
            "read_at",
            "created_at",
        ]
        read_only_fields = fields

    def get_navigation(self, obj):
        metadata = obj.metadata if isinstance(obj.metadata, dict) else {}
        identifiers = {
            key: metadata.get(key)
            for key in ("event_id", "order_id", "payment_id", "ticket_id")
            if metadata.get(key)
        }
        if not identifiers:
            return None

        if identifiers.get("ticket_id"):
            target = "ticket"
        elif identifiers.get("payment_id"):
            target = "payment"
        elif identifiers.get("order_id"):
            target = "order"
        else:
            target = "event"
        return {"target": target, **identifiers}
