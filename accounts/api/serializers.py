from django.contrib.auth.password_validation import validate_password
from datetime import timedelta

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from accounts.models import (
    NotificationPreference,
    User,
    UserDevice,
    UserProfile,
    UserSession,
)
from accounts.validators import (
    normalize_makolo_username,
    validate_avatar,
    validate_makolo_username,
)


class MakoloTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Accept an Identifiant Makolo or e-mail without making either a second identity."""

    username = serializers.CharField(required=False, allow_blank=False)
    email = serializers.EmailField(required=False, write_only=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # SimpleJWT derives this field from USERNAME_FIELD and marks it required.
        # Makolo also accepts the historical e-mail payload, so requirement is
        # enforced only after the two supported login keys are resolved.
        self.fields["username"].required = False

    def validate(self, attrs):
        login = attrs.get("username") or attrs.pop("email", None)
        if not login:
            raise serializers.ValidationError(
                {"username": "Saisissez votre Identifiant Makolo ou votre adresse e-mail."}
            )
        attrs["username"] = login
        return super().validate(attrs)


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
            "id", "email", "username", "username_configured", "first_name", "last_name", "full_name",
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
            "id", "email", "username", "username_configured", "username_changed_at",
            "first_name", "last_name", "full_name", "phone",
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
    email = serializers.EmailField(required=False, allow_blank=True, allow_null=True)
    username = serializers.CharField(max_length=30)
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = [
            "email", "username", "password", "password_confirm", "first_name", "last_name", "phone",
        ]

    def validate_username(self, value):
        normalized = normalize_makolo_username(value)
        try:
            validate_makolo_username(normalized)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc
        if User.objects.filter(username__iexact=normalized).exists():
            raise serializers.ValidationError("Cet identifiant Makolo est déjà utilisé.")
        from sharing.models import PublicIdentifier
        if PublicIdentifier.objects.filter(identifier__iexact=normalized).exists():
            raise serializers.ValidationError("Cet identifiant Makolo est déjà utilisé.")
        return normalized

    def validate_email(self, value):
        normalized = (value or "").strip().lower()
        if normalized and User.objects.filter(email__iexact=normalized).exists():
            raise serializers.ValidationError("Cette adresse e-mail est déjà utilisée.")
        return normalized or None

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({"password": "Les mots de passe ne correspondent pas."})
        try:
            validate_password(attrs["password"])
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)}) from exc
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        validated_data.pop("password_confirm")
        password = validated_data.pop("password")
        user = User(
            **validated_data,
            username_configured=True,
            username_changed_at=timezone.now(),
        )
        user.set_password(password)
        try:
            user.save()
        except IntegrityError as exc:
            raise serializers.ValidationError(
                {"username": "Cet identifiant Makolo n’est plus disponible."}
            ) from exc
        UserProfile.objects.create(user=user)
        NotificationPreference.objects.create(user=user)
        return user


class MakoloIdentifierSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=30)

    def validate_username(self, value):
        normalized = normalize_makolo_username(value)
        try:
            validate_makolo_username(normalized)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc
        return normalized


class MakoloIdentifierChangeSerializer(MakoloIdentifierSerializer):
    def validate_username(self, value):
        normalized = super().validate_username(value)
        request = self.context["request"]
        user = request.user
        if User.objects.filter(username__iexact=normalized).exclude(pk=user.pk).exists():
            raise serializers.ValidationError("Cet identifiant Makolo est déjà utilisé.")
        from sharing.models import PublicIdentifier
        if PublicIdentifier.objects.filter(identifier__iexact=normalized).exclude(profile_id=user.pk).exists():
            raise serializers.ValidationError("Cet identifiant Makolo est déjà utilisé.")
        if user.username_configured and user.username_changed_at:
            next_change_at = user.username_changed_at + timedelta(days=90)
            if timezone.now() < next_change_at:
                raise serializers.ValidationError(
                    f"Vous pourrez modifier votre identifiant Makolo à partir du {next_change_at.date().isoformat()}."
                )
        return normalized

    @transaction.atomic
    def save(self, **kwargs):
        user = User.objects.select_for_update().get(pk=self.context["request"].user.pk)
        username = self.validated_data["username"]
        if User.objects.filter(username__iexact=username).exclude(pk=user.pk).exists():
            raise serializers.ValidationError(
                {"username": "Cet identifiant Makolo n’est plus disponible."}
            )
        from sharing.models import PublicIdentifier
        if PublicIdentifier.objects.filter(identifier__iexact=username).exclude(profile_id=user.pk).exists():
            raise serializers.ValidationError(
                {"username": "Cet identifiant Makolo n’est plus disponible."}
            )
        user.username = username
        user.username_configured = True
        user.username_changed_at = timezone.now()
        try:
            user.save(update_fields=["username", "username_configured", "username_changed_at", "updated_at"])
        except IntegrityError as exc:
            raise serializers.ValidationError(
                {"username": "Cet identifiant Makolo n’est plus disponible."}
            ) from exc
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
