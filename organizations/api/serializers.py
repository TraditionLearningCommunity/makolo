from rest_framework import serializers


class OrganizationFollowSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    organization_id = serializers.UUIDField(read_only=True)
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    organization_slug = serializers.CharField(source="organization.slug", read_only=True)
    notify_new_events = serializers.BooleanField(read_only=True)
    notify_announcements = serializers.BooleanField(read_only=True)
    email_new_events = serializers.BooleanField(read_only=True)
    email_announcements = serializers.BooleanField(read_only=True)
    followed_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)


class OrganizationFollowCreateSerializer(serializers.Serializer):
    organization_id = serializers.UUIDField()
    notify_new_events = serializers.BooleanField(required=False, default=True)
    notify_announcements = serializers.BooleanField(required=False, default=True)
    email_new_events = serializers.BooleanField(required=False, default=False)
    email_announcements = serializers.BooleanField(required=False, default=False)


class OrganizationFollowPreferenceSerializer(serializers.Serializer):
    notify_new_events = serializers.BooleanField(required=False)
    notify_announcements = serializers.BooleanField(required=False)
    email_new_events = serializers.BooleanField(required=False)
    email_announcements = serializers.BooleanField(required=False)
