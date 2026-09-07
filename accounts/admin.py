import csv

from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.http import HttpResponse
from django.utils.html import format_html

from .models import (
    NotificationPreference,
    User,
    UserDevice,
    UserProfile,
    UserSession,
)


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    extra = 0
    can_delete = False


class NotificationPreferenceInline(admin.StackedInline):
    model = NotificationPreference
    extra = 0
    can_delete = False


class UserDeviceInline(admin.TabularInline):
    model = UserDevice
    extra = 0
    readonly_fields = (
        "device_name",
        "device_type",
        "browser",
        "os",
        "ip_address",
        "trusted",
        "last_used",
        "created_at",
    )


class UserSessionInline(admin.TabularInline):
    model = UserSession
    extra = 0
    readonly_fields = (
        "session_key",
        "ip_address",
        "started_at",
        "ended_at",
        "active",
    )


@admin.action(description="Activate selected users")
def activate_users(modeladmin, request, queryset):
    updated = queryset.update(is_active=True)
    messages.success(request, f"{updated} users activated.")


@admin.action(description="Deactivate selected users")
def deactivate_users(modeladmin, request, queryset):
    updated = queryset.update(is_active=False)
    messages.warning(request, f"{updated} users deactivated.")


@admin.action(description="Mark email as verified")
def verify_email(modeladmin, request, queryset):
    updated = queryset.update(email_verified=True)
    messages.success(request, f"{updated} email(s) verified.")


@admin.action(description="Reset failed login attempts")
def reset_login_attempts(modeladmin, request, queryset):
    updated = queryset.update(failed_login_attempts=0, account_locked_until=None)
    messages.success(request, f"{updated} account(s) unlocked.")


@admin.action(description="Export selected users to CSV")
def export_users_csv(modeladmin, request, queryset):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="users.csv"'
    writer = csv.writer(response)
    writer.writerow(["ID", "Email", "Username", "Phone", "Active", "Date Joined"])
    for user in queryset:
        writer.writerow([
            user.id,
            user.email,
            user.username,
            user.phone,
            user.is_active,
            user.date_joined,
        ])
    return response


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Technical account administration only.

    Business authority is administered through authorization Role/Mandate and
    identity assurance through Trust. Accounts admin intentionally exposes
    neither of those as mutable User fields.
    """

    list_display = (
        "avatar_preview",
        "email",
        "username",
        "full_name_display",
        "active_badge",
        "staff_badge",
        "email_verified",
        "phone_verified",
        "last_seen",
        "created_at",
    )
    list_display_links = ("email", "username")
    list_per_page = 25
    ordering = ("-created_at",)
    date_hierarchy = "created_at"
    list_filter = (
        "email_verified",
        "phone_verified",
        "is_active",
        "is_staff",
        "is_superuser",
        "language",
        "created_at",
    )
    search_fields = ("email", "username", "first_name", "last_name", "phone")
    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
        "last_login",
        "date_joined",
        "avatar_preview_large",
    )
    filter_horizontal = ("groups", "user_permissions")
    inlines = [
        UserProfileInline,
        NotificationPreferenceInline,
        UserDeviceInline,
        UserSessionInline,
    ]
    actions = [
        activate_users,
        deactivate_users,
        verify_email,
        reset_login_attempts,
        export_users_csv,
    ]

    fieldsets = (
        ("Identity", {
            "fields": (
                "id", "email", "username", "password", "first_name", "last_name",
                "phone", "birth_date", "gender", "bio", "avatar", "avatar_preview_large",
            )
        }),
        ("Contact verification", {"fields": ("email_verified", "phone_verified")}),
        ("Django technical permissions", {
            "fields": ("groups", "user_permissions", "is_staff", "is_superuser", "is_active")
        }),
        ("Security", {
            "fields": (
                "last_login", "last_login_ip", "failed_login_attempts",
                "account_locked_until", "require_2fa",
            )
        }),
        ("Preferences", {"fields": ("language", "timezone", "preferences")}),
        ("Social", {
            "fields": (
                "website", "linkedin_url", "facebook_url", "instagram_url",
                "tiktok_url", "x_url", "youtube_url",
            )
        }),
        ("Metadata", {"classes": ("collapse",), "fields": ("metadata",)}),
        ("Dates", {"fields": ("last_seen", "date_joined", "created_at", "updated_at")}),
    )

    add_fieldsets = (
        (
            "Create User",
            {
                "classes": ("wide",),
                "fields": (
                    "email", "username", "password1", "password2",
                    "is_staff", "is_superuser", "is_active",
                ),
            },
        ),
    )

    def avatar_preview(self, obj):
        if obj.avatar:
            return format_html(
                '<img src="{}" style="width:40px;height:40px;border-radius:50%;object-fit:cover;" />',
                obj.avatar.url,
            )
        return "—"

    avatar_preview.short_description = "Avatar"

    def avatar_preview_large(self, obj):
        if obj.avatar:
            return format_html(
                '<img src="{}" style="width:120px;height:120px;border-radius:12px;object-fit:cover;" />',
                obj.avatar.url,
            )
        return "No avatar"

    avatar_preview_large.short_description = "Preview"

    def full_name_display(self, obj):
        return obj.full_name or "-"

    full_name_display.short_description = "Full Name"

    def active_badge(self, obj):
        color = "#2563eb" if obj.is_active else "#6b7280"
        text = "Active" if obj.is_active else "Disabled"
        return format_html(
            '<span style="color:white;background:{};padding:4px 8px;border-radius:8px;">{}</span>',
            color,
            text,
        )

    active_badge.short_description = "Status"

    def staff_badge(self, obj):
        if obj.is_staff:
            return format_html('<span style="color:#f59e0b;font-weight:bold;">STAFF</span>')
        return "-"

    staff_badge.short_description = "Staff"


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "country", "city", "profession", "completion_status", "public_profile")
    list_filter = ("country", "public_profile")
    search_fields = ("user__email", "company_name", "organization_name")

    @admin.display(boolean=True, description="Profile complete")
    def completion_status(self, obj):
        return obj.derive_profile_completed()


@admin.register(UserDevice)
class UserDeviceAdmin(admin.ModelAdmin):
    list_display = ("user", "device_name", "device_type", "browser", "os", "trusted", "last_used")
    list_filter = ("trusted", "device_type", "os")
    search_fields = ("user__email", "device_name", "ip_address")


@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    list_display = ("user", "ip_address", "started_at", "ended_at", "active")
    list_filter = ("active", "started_at")
    readonly_fields = (
        "session_key", "user", "ip_address", "user_agent", "started_at",
        "ended_at", "metadata",
    )
    search_fields = ("user__email", "ip_address")


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = (
        "user", "email_notifications", "sms_notifications", "push_notifications",
        "marketing_notifications",
    )
    list_filter = (
        "email_notifications", "sms_notifications", "push_notifications", "marketing_notifications",
    )
    search_fields = ("user__email",)
