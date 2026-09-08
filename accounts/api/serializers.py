from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction

from rest_framework import serializers

from accounts.models import (
    NotificationPreference,
    User,
    UserDevice,
    UserProfile,
    UserSession,
)
from accounts.validators import validate_avatar


class UserProfileSerializer(serializers.ModelSerializer):
    profile_completed = serializers.SerializerMethodField()

    class Meta:
        model = UserProfile
        fields = [
            "id", "company_name", "organization_name", "profession", "country",
            "city", "address", "latitude", "longitude", "theme", "profile_completed",
            "public_profile", "searchable", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_profile_completed(self, obj):
        return obj.derive_profile_completed()


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreference
        fields = [
            "id", "email_notifications", "sms_notifications", "push_notifications",
            "marketing_notifications", "security_notifications", "event_notifications",
            "service_notifications", "opportunity_notifications",
            "quiet_hours_enabled", "quiet_hours_start", "quiet_hours_end",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs):
        instance = self.instance
        enabled = attrs.get("quiet_hours_enabled", getattr(instance, "quiet_hours_enabled", False))
        start = attrs.get("quiet_hours_start", getattr(instance, "quiet_hours_start", None))
        end = attrs.get("quiet_hours_end", getattr(instance, "quiet_hours_end", None))
        if enabled and (start is None or end is None):
            raise serializers.ValidationError(
                {"quiet_hours_enabled": "Définissez une heure de début et de fin pour activer les heures calmes."}
            )
        return attrs


class UserDeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserDevice
        fields = [
            "id", "device_name", "device_type", "browser", "os", "ip_address",
            "trusted", "last_used", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class UserSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserSession
        fields = [
            "id", "ip_address", "started_at", "ended_at", "active", "created_at", "updated_at",
        ]
        read_only_fields = fields


class UserListSerializer(serializers.ModelSerializer):
    avatar_url = serializers.SerializerMethodField()
    full_name = serializers.ReadOnlyField()

    class Meta:
        model = User
        fields = [
            "id", "email", "username", "first_name", "last_name", "full_name",
            "phone", "avatar_url", "is_active", "last_seen", "created_at",
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
    profile = UserProfileSerializer(read_only=True)
    notification_preferences = NotificationPreferenceSerializer(read_only=True)

    class Meta:
        model = User
        fields = [
            "id", "email", "username", "first_name", "last_name", "full_name", "phone",
            "birth_date", "gender", "bio", "avatar_url", "language", "timezone", "is_active",
            "email_verified", "phone_verified", "onboarding_completed", "onboarding_step", "last_seen",
            "website", "linkedin_url", "facebook_url", "instagram_url", "tiktok_url", "x_url",
            "youtube_url", "profile", "notification_preferences", "created_at", "updated_at",
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
            "email", "username", "password", "password_confirm", "first_name", "last_name", "phone",
        ]

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({"password": "Les mots de passe ne correspondent pas."})
        try:
            validate_password(attrs["password"])
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)}) from exc
        attrs["email"] = attrs["email"].strip().lower()
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
            "first_name", "last_name", "phone", "bio", "avatar", "birth_date", "gender",
            "website", "linkedin_url", "facebook_url", "instagram_url", "tiktok_url", "x_url",
            "youtube_url", "language", "timezone",
        ]

    def validate_avatar(self, value):
        try:
            validate_avatar(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc
        return value

    @transaction.atomic
    def update(self, instance, validated_data):
        user = super().update(instance, validated_data)
        UserProfile.objects.get_or_create(user=user)
        return user


class ProfileUpdateSerializer(UserUpdateSerializer):
    """Private/self Profile editor spanning User and UserProfile storage."""

    company_name = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=255)
    organization_name = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=255)
    profession = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=255)
    country = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=100)
    city = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=100)
    address = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    public_profile = serializers.BooleanField(required=False)
    searchable = serializers.BooleanField(required=False)

    profile_fields = (
        "company_name", "organization_name", "profession", "country", "city", "address",
        "public_profile", "searchable",
    )

    class Meta(UserUpdateSerializer.Meta):
        fields = [
            *UserUpdateSerializer.Meta.fields,
            "company_name", "organization_name", "profession", "country", "city", "address",
            "public_profile", "searchable",
        ]

    @transaction.atomic
    def update(self, instance, validated_data):
        profile_data = {}
        for field_name in self.profile_fields:
            if field_name in validated_data:
                profile_data[field_name] = validated_data.pop(field_name)

        user = super().update(instance, validated_data)
        profile, _ = UserProfile.objects.get_or_create(user=user)
        for field_name, value in profile_data.items():
            setattr(profile, field_name, value)
        profile.save()
        return user


class PasswordForgotSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetSerializer(serializers.Serializer):
    uid = serializers.CharField(max_length=200)
    token = serializers.CharField(max_length=200)
    new_password = serializers.CharField(write_only=True, min_length=8)
    new_password_confirm = serializers.CharField(write_only=True)

    def validate(self, attrs):
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError({"new_password": "Les mots de passe ne correspondent pas."})
        return attrs


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)
    new_password_confirm = serializers.CharField(write_only=True)

    def validate(self, attrs):
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError({"new_password": "Les mots de passe ne correspondent pas."})
        request = self.context.get("request")
        try:
            validate_password(attrs["new_password"], user=request.user if request else None)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"new_password": list(exc.messages)}) from exc
        return attrs


class AccountDeleteSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True)
