from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.utils import timezone
from django.db.models import Count
from django.http import HttpResponse
import csv

from .models import (
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
# INLINE MODELS
# =========================================================

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


# =========================================================
# USER ADMIN ACTIONS
# =========================================================

@admin.action(description="Verify selected users")
def verify_users(modeladmin, request, queryset):
    updated = queryset.update(is_verified=True)
    messages.success(
        request,
        f"{updated} users verified successfully."
    )


@admin.action(description="Unverify selected users")
def unverify_users(modeladmin, request, queryset):
    updated = queryset.update(is_verified=False)
    messages.warning(
        request,
        f"{updated} users unverified."
    )


@admin.action(description="Activate selected users")
def activate_users(modeladmin, request, queryset):
    updated = queryset.update(is_active=True)

    messages.success(
        request,
        f"{updated} users activated."
    )


@admin.action(description="Deactivate selected users")
def deactivate_users(modeladmin, request, queryset):
    updated = queryset.update(is_active=False)

    messages.warning(
        request,
        f"{updated} users deactivated."
    )


@admin.action(description="Mark email as verified")
def verify_email(modeladmin, request, queryset):
    updated = queryset.update(email_verified=True)

    messages.success(
        request,
        f"{updated} email(s) verified."
    )


@admin.action(description="Reset failed login attempts")
def reset_login_attempts(modeladmin, request, queryset):
    updated = queryset.update(
        failed_login_attempts=0,
        account_locked_until=None
    )

    messages.success(
        request,
        f"{updated} account(s) unlocked."
    )


@admin.action(description="Export selected users to CSV")
def export_users_csv(modeladmin, request, queryset):

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="users.csv"'

    writer = csv.writer(response)

    writer.writerow([
        "ID",
        "Email",
        "Username",
        "Phone",
        "Verified",
        "Active",
        "Date Joined",
    ])

    for user in queryset:
        writer.writerow([
            user.id,
            user.email,
            user.username,
            user.phone,
            user.is_verified,
            user.is_active,
            user.date_joined,
        ])

    return response


# =========================================================
# ROLE ADMIN
# =========================================================

@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):

    list_display = (
        "name",
        "code",
        "priority",
        "is_system",
        "is_active",
        "users_count",
        "created_at",
    )

    list_filter = (
        "is_system",
        "is_active",
    )

    search_fields = (
        "name",
        "code",
    )

    ordering = (
        "priority",
        "name",
    )

    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
    )

    filter_horizontal = ()

    def users_count(self, obj):
        return obj.users.count()

    users_count.short_description = "Users"


# =========================================================
# PERMISSION GROUP ADMIN
# =========================================================

@admin.register(PermissionGroup)
class PermissionGroupAdmin(admin.ModelAdmin):

    list_display = (
        "name",
        "code",
        "roles_count",
        "users_count",
        "created_at",
    )

    search_fields = (
        "name",
        "code",
    )

    filter_horizontal = (
        "roles",
    )

    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
    )

    def roles_count(self, obj):
        return obj.roles.count()

    def users_count(self, obj):
        return obj.users.count()


# =========================================================
# USER ADMIN
# =========================================================

@admin.register(User)
class UserAdmin(BaseUserAdmin):

    # =====================================================
    # DISPLAY
    # =====================================================

    list_display = (
        "avatar_preview",
        "email",
        "username",
        "full_name_display",
        "verified_badge",
        "active_badge",
        "staff_badge",
        "roles_display",
        "last_seen",
        "created_at",
    )

    list_display_links = (
        "email",
        "username",
    )

    list_per_page = 25

    ordering = (
        "-created_at",
    )

    date_hierarchy = "created_at"

    # =====================================================
    # FILTERS
    # =====================================================

    list_filter = (
        "is_verified",
        "email_verified",
        "phone_verified",
        "is_active",
        "is_staff",
        "is_superuser",
        "is_organizer",
        "is_scanner_agent",
        "language",
        "created_at",
    )

    # =====================================================
    # SEARCH
    # =====================================================

    search_fields = (
        "email",
        "username",
        "first_name",
        "last_name",
        "phone",
    )

    # =====================================================
    # READONLY
    # =====================================================

    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
        "last_login",
        "date_joined",
        "avatar_preview_large",
    )

    # =====================================================
    # MANY TO MANY
    # =====================================================

    filter_horizontal = (
        "groups",
        "user_permissions",
        "roles",
        "permission_groups",
    )

    # =====================================================
    # INLINES
    # =====================================================

    inlines = [
        UserProfileInline,
        NotificationPreferenceInline,
        UserDeviceInline,
        UserSessionInline,
    ]

    # =====================================================
    # ACTIONS
    # =====================================================

    actions = [
        verify_users,
        unverify_users,
        activate_users,
        deactivate_users,
        verify_email,
        reset_login_attempts,
        export_users_csv,
    ]

    # =====================================================
    # FIELDSETS
    # =====================================================

    fieldsets = (

        ("Identity", {
            "fields": (
                "id",
                "email",
                "username",
                "password",
                "first_name",
                "last_name",
                "phone",
                "birth_date",
                "gender",
                "bio",
                "avatar",
                "avatar_preview_large",
            )
        }),

        ("Verification", {
            "fields": (
                "is_verified",
                "email_verified",
                "phone_verified",
            )
        }),

        ("Roles & Permissions", {
            "fields": (
                "roles",
                "permission_groups",
                "groups",
                "user_permissions",
                "is_staff",
                "is_superuser",
                "is_active",
                "is_organizer",
                "is_scanner_agent",
            )
        }),

        ("Security", {
            "fields": (
                "last_login",
                "last_login_ip",
                "failed_login_attempts",
                "account_locked_until",
                "require_2fa",
            )
        }),

        ("Preferences", {
            "fields": (
                "language",
                "timezone",
                "preferences",
                "settings_data",
            )
        }),

        ("Social", {
            "fields": (
                "website",
                "linkedin_url",
                "facebook_url",
                "instagram_url",
                "x_url",
            )
        }),

        ("Metadata", {
            "classes": ("collapse",),
            "fields": (
                "metadata",
                "analytics_data",
            )
        }),

        ("Dates", {
            "fields": (
                "last_seen",
                "date_joined",
                "created_at",
                "updated_at",
            )
        }),
    )

    # =====================================================
    # ADD FIELDSETS
    # =====================================================

    add_fieldsets = (
        (
            "Create User",
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "username",
                    "password1",
                    "password2",
                    "is_staff",
                    "is_superuser",
                    "is_active",
                ),
            },
        ),
    )

    # =====================================================
    # CUSTOM METHODS
    # =====================================================

    def verified_badge(self, obj):

        if obj.is_verified:
            color = "#16a34a"
            text = "Verified"
        else:
            color = "#dc2626"
            text = "Unverified"

        return format_html(
            f'<span style="color:white;background:{color};padding:4px 8px;border-radius:8px;">{text}</span>'
        )

    verified_badge.short_description = "Verification"

    def active_badge(self, obj):

        if obj.is_active:
            color = "#2563eb"
            text = "Active"
        else:
            color = "#6b7280"
            text = "Disabled"

        return format_html(
            f'<span style="color:white;background:{color};padding:4px 8px;border-radius:8px;">{text}</span>'
        )

    active_badge.short_description = "Status"

    def staff_badge(self, obj):

        if obj.is_staff:
            return format_html(
                '<span style="color:#f59e0b;font-weight:bold;">STAFF</span>'
            )

        return "-"

    staff_badge.short_description = "Staff"

    def roles_display(self, obj):

        roles = obj.roles.all()[:3]

        if not roles:
            return "-"

        return ", ".join([r.name for r in roles])

    roles_display.short_description = "Roles"

    def avatar_preview(self, obj):

        if obj.avatar:
            return format_html(
                '<img src="{}" style="width:40px;height:40px;border-radius:50%;object-fit:cover;" />',
                obj.avatar.url
            )

        return "—"

    avatar_preview.short_description = "Avatar"

    def avatar_preview_large(self, obj):

        if obj.avatar:
            return format_html(
                '<img src="{}" style="width:120px;height:120px;border-radius:12px;object-fit:cover;" />',
                obj.avatar.url
            )

        return "No avatar"

    avatar_preview_large.short_description = "Preview"

    def full_name_display(self, obj):
        return obj.full_name or "-"

    full_name_display.short_description = "Full Name"

    # =====================================================
    # QUERYSET OPTIMIZATION
    # =====================================================

    def get_queryset(self, request):

        queryset = super().get_queryset(request)

        return queryset.prefetch_related(
            "roles",
            "permission_groups",
        )


# =========================================================
# USER PROFILE ADMIN
# =========================================================

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):

    list_display = (
        "user",
        "country",
        "city",
        "profession",
        "profile_completed",
        "public_profile",
    )

    list_filter = (
        "country",
        "profile_completed",
        "public_profile",
    )

    search_fields = (
        "user__email",
        "company_name",
        "organization_name",
    )


# =========================================================
# USER DEVICE ADMIN
# =========================================================

@admin.register(UserDevice)
class UserDeviceAdmin(admin.ModelAdmin):

    list_display = (
        "user",
        "device_name",
        "device_type",
        "browser",
        "os",
        "trusted",
        "last_used",
    )

    list_filter = (
        "trusted",
        "device_type",
        "os",
    )

    search_fields = (
        "user__email",
        "device_name",
        "ip_address",
    )


# =========================================================
# USER SESSION ADMIN
# =========================================================

@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):

    list_display = (
        "user",
        "ip_address",
        "started_at",
        "ended_at",
        "active",
    )

    list_filter = (
        "active",
        "started_at",
    )

    readonly_fields = (
        "session_key",
        "user",
        "ip_address",
        "user_agent",
        "started_at",
        "ended_at",
        "metadata",
    )

    search_fields = (
        "user__email",
        "ip_address",
    )


# =========================================================
# VERIFICATION DOCUMENT ADMIN
# =========================================================

@admin.register(VerificationDocument)
class VerificationDocumentAdmin(admin.ModelAdmin):

    list_display = (
        "user",
        "document_type",
        "status",
        "reviewed_by",
        "reviewed_at",
        "created_at",
    )

    list_filter = (
        "status",
        "document_type",
    )

    search_fields = (
        "user__email",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    actions = [
        "approve_documents",
        "reject_documents",
    ]

    @admin.action(description="Approve selected documents")
    def approve_documents(self, request, queryset):

        queryset.update(
            status="approved",
            reviewed_by=request.user,
            reviewed_at=timezone.now(),
        )

        messages.success(
            request,
            "Documents approved successfully."
        )

    @admin.action(description="Reject selected documents")
    def reject_documents(self, request, queryset):

        queryset.update(
            status="rejected",
            reviewed_by=request.user,
            reviewed_at=timezone.now(),
        )

        messages.warning(
            request,
            "Documents rejected."
        )


# =========================================================
# USER ACTIVITY ADMIN
# =========================================================

@admin.register(UserActivity)
class UserActivityAdmin(admin.ModelAdmin):

    list_display = (
        "user",
        "action",
        "category",
        "ip_address",
        "created_at",
    )

    list_filter = (
        "category",
        "created_at",
    )

    search_fields = (
        "user__email",
        "action",
    )

    readonly_fields = (
        "user",
        "action",
        "category",
        "ip_address",
        "user_agent",
        "metadata",
        "created_at",
    )

    ordering = (
        "-created_at",
    )


# =========================================================
# NOTIFICATION PREFERENCES ADMIN
# =========================================================

@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):

    list_display = (
        "user",
        "email_notifications",
        "sms_notifications",
        "push_notifications",
        "marketing_notifications",
    )

    list_filter = (
        "email_notifications",
        "sms_notifications",
        "push_notifications",
        "marketing_notifications",
    )

    search_fields = (
        "user__email",
    )