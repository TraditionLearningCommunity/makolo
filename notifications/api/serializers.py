from rest_framework import serializers

from notifications.models import Notification, PushEndpoint, PushPlatform, PushProvider
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


class PushEndpointRegistrationSerializer(serializers.Serializer):
    provider = serializers.ChoiceField(choices=PushProvider.choices, default=PushProvider.FCM)
    platform = serializers.ChoiceField(choices=PushPlatform.choices)
    installation_id = serializers.CharField(max_length=128)
    token = serializers.CharField(write_only=True, trim_whitespace=True)
    app_version = serializers.CharField(max_length=64, required=False, allow_blank=True)


class PushEndpointRevokeSerializer(serializers.Serializer):
    provider = serializers.ChoiceField(choices=PushProvider.choices, default=PushProvider.FCM)
    installation_id = serializers.CharField(max_length=128)


class PushEndpointSerializer(serializers.ModelSerializer):
    class Meta:
        model = PushEndpoint
        fields = [
            "id",
            "provider",
            "platform",
            "installation_id",
            "token_hint",
            "app_version",
            "active",
            "last_seen_at",
        ]
        read_only_fields = fields
