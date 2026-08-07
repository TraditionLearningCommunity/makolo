from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction

from rest_framework import serializers

from accounts.models import (
    User,
    Role,
    PermissionGroup,
    UserProfile,
    UserDevice,
    UserSession,
    VerificationDocument,
    UserActivity,
    NotificationPreference,
)


# =========================================================
# ROLE
# =========================================================

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

        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
        ]

    def get_users_count(self, obj):
        return obj.users.count()


# =========================================================
# PERMISSION GROUP
# =========================================================

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

        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
        ]


# =========================================================
# USER PROFILE
# =========================================================

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

        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
        ]


# =========================================================
# NOTIFICATION PREFERENCES
# =========================================================

class NotificationPreferenceSerializer(serializers.ModelSerializer):

    class Meta:
        model = NotificationPreference

        fields = "__all__"

        read_only_fields = [
            "id",
            "user",
            "created_at",
            "updated_at",
        ]


# =========================================================
# USER DEVICE
# =========================================================

class UserDeviceSerializer(serializers.ModelSerializer):

    class Meta:
        model = UserDevice

        fields = "__all__"

        read_only_fields = [
            "id",
            "user",
            "created_at",
            "updated_at",
        ]


# =========================================================
# USER SESSION
# =========================================================

class UserSessionSerializer(serializers.ModelSerializer):

    class Meta:
        model = UserSession

        fields = "__all__"

        read_only_fields = [
            "id",
            "user",
            "created_at",
            "updated_at",
        ]


# =========================================================
# VERIFICATION DOCUMENT
# =========================================================

class VerificationDocumentSerializer(serializers.ModelSerializer):

    class Meta:
        model = VerificationDocument

        fields = "__all__"

        read_only_fields = [
            "id",
            "status",
            "reviewed_by",
            "reviewed_at",
            "created_at",
            "updated_at",
        ]


# =========================================================
# USER ACTIVITY
# =========================================================

class UserActivitySerializer(serializers.ModelSerializer):

    class Meta:
        model = UserActivity

        fields = "__all__"

        read_only_fields = [
            "id",
            "user",
            "created_at",
            "updated_at",
        ]


# =========================================================
# USER LIST
# =========================================================

class UserListSerializer(serializers.ModelSerializer):

    avatar_url = serializers.SerializerMethodField()
    full_name = serializers.ReadOnlyField()

    roles = RoleSerializer(
        many=True,
        read_only=True
    )

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

        request = self.context.get("request")

        if obj.avatar:
            return request.build_absolute_uri(
                obj.avatar.url
            )

        return None


# =========================================================
# USER DETAIL
# =========================================================

class UserDetailSerializer(serializers.ModelSerializer):

    avatar_url = serializers.SerializerMethodField()

    full_name = serializers.ReadOnlyField()

    roles = RoleSerializer(
        many=True,
        read_only=True
    )

    permission_groups = PermissionGroupSerializer(
        many=True,
        read_only=True
    )

    profile = UserProfileSerializer(
        read_only=True
    )

    notification_preferences = NotificationPreferenceSerializer(
        read_only=True
    )

    class Meta:
        model = User

        exclude = [
            "password",
            "groups",
            "user_permissions",
        ]

    def get_avatar_url(self, obj):

        request = self.context.get("request")

        if obj.avatar:
            return request.build_absolute_uri(
                obj.avatar.url
            )

        return None


# =========================================================
# USER REGISTER
# =========================================================

class RegisterSerializer(serializers.ModelSerializer):

    password = serializers.CharField(
        write_only=True,
        min_length=8
    )

    password_confirm = serializers.CharField(
        write_only=True
    )

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
                {
                    "password":
                    "Passwords do not match."
                }
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

        UserProfile.objects.create(
            user=user
        )

        NotificationPreference.objects.create(
            user=user
        )

        return user


# =========================================================
# USER UPDATE
# =========================================================

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
