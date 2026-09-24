from rest_framework import serializers

from notifications.models import Notification
from notifications.navigation import build_notification_navigation


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
        return build_notification_navigation(obj)
