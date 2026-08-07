from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction

from rest_framework import serializers

from accounts.models import (
    NotificationPreference,
    PermissionGroup,
    Role,
    User,
    UserActivity,
    UserDevice,
    UserProfile,
    UserSession,
    VerificationDocument,
)
from accounts.validators import validate_avatar, validate_verification_document


class RoleSerializer(serializers.ModelSerializer):
    users_count = serializers.SerializerMethodField()

    class Meta:
        model = Role
        fields = [
            "id",
            "name",
            "code",
            "description",
            "priority",
            "is_system",
            "is_active",
            "users_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_users_count(self, obj):
        return obj.users.count()


class PermissionGroupSerializer(serializers.ModelSerializer):
    roles = RoleSerializer(many=True, read_only=True)

    class Meta:
        model = PermissionGroup
        fields = [
            "id",
            "name",
            "code",
            "description",
            "roles",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = [
            "id",
            "company_name",
            "organization_name",
            "profession",
            "country",
            "city",
            "address",
            "latitude",
            "longitude",
            "theme",
            "profile_completed",
            "public_profile",
            "searchable",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreference
        fields = [
            "id",
            "email_notifications",
            "sms_notifications",
            "push_notifications",
            "marketing_notifications",
            "security_notifications",
            "event_notifications",
            "quiet_hours_enabled",
            "quiet_hours_start",
            "quiet_hours_end",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class UserDeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserDevice
        fields = [
            "id",
            "device_name",
            "device_type",
            "browser",
            "os",
            "ip_address",
            "trusted",
            "last_used",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class UserSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserSession
        fields = [
            "id",
            "ip_address",
            "started_at",
            "ended_at",
            "active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class VerificationDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = VerificationDocument
        fields = [
            "id",
            "document_type",
            "file",
            "status",
            "reviewed_at",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "reviewed_at",
            "notes",
            "created_at",
            "updated_at",
        ]

    def validate_file(self, value):
        try:
            validate_verification_document(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc
        return value


class UserActivitySerializer(serializers.ModelSerializer):
    class Meta:
        model = UserActivity
        fields = [
            "id",
            "action",
            "category",
            "ip_address",
            "created_at",
        ]
        read_only_fields = fields


class UserListSerializer(serializers.ModelSerializer):
    avatar_url = serializers.SerializerMethodField()
    full_name = serializers.ReadOnlyField()
    roles = RoleSerializer(many=True, read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "username",
            "first_name",
            "last_name",
            "full_name",
            "phone",
            "avatar_url",
            "is_verified",
            "is_active",
            "is_organizer",
            "is_scanner_agent",
            "roles",
            "last_seen",
            "created_at",
        ]

    def get_avatar_url(self, obj):
        if not obj.avatar:
            return None

        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(obj.avatar.url)
        return obj.avatar.url


class UserDetailSerializer(serializers.ModelSerializer):
    avatar_url = serializers.SerializerMethodField()
    full_name = serializers.ReadOnlyField()
    roles = RoleSerializer(many=True, read_only=True)
    permission_groups = PermissionGroupSerializer(many=True, read_only=True)
    profile = UserProfileSerializer(read_only=True)
    notification_preferences = NotificationPreferenceSerializer(read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "username",
            "first_name",
            "last_name",
            "full_name",
            "phone",
            "birth_date",
            "gender",
            "bio",
            "avatar_url",
            "language",
            "timezone",
            "is_active",
            "is_verified",
            "email_verified",
            "phone_verified",
            "is_organizer",
            "is_scanner_agent",
            "onboarding_completed",
            "onboarding_step",
            "last_seen",
            "website",
            "linkedin_url",
            "facebook_url",
            "instagram_url",
            "x_url",
            "roles",
            "permission_groups",
            "profile",
            "notification_preferences",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_avatar_url(self, obj):
        if not obj.avatar:
            return None

        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(obj.avatar.url)
        return obj.avatar.url


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = [
            "email",
            "username",
            "password",
            "password_confirm",
            "first_name",
            "last_name",
            "phone",
        ]

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError(
                {"password": "Passwords do not match."}
            )

        try:
            validate_password(attrs["password"])
        except DjangoValidationError as exc:
            raise serializers.ValidationError(
                {"password": list(exc.messages)}
            ) from exc

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        validated_data.pop("password_confirm")
        password = validated_data.pop("password")

        user = User(**validated_data)
        user.set_password(password)
        user.save()

        UserProfile.objects.create(user=user)
        NotificationPreference.objects.create(user=user)
        return user


class UserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "first_name",
            "last_name",
            "phone",
            "bio",
            "avatar",
            "birth_date",
            "gender",
            "website",
            "linkedin_url",
            "facebook_url",
            "instagram_url",
            "x_url",
            "language",
            "timezone",
        ]

    def validate_avatar(self, value):
        try:
            validate_avatar(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc
        return value
