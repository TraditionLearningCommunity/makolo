from django.contrib import admin

from .models import (
    Organization,
    OrganizationFollow,
    OrganizationMembership,
    Team,
    TeamMembership,
)


class ReadOnlyCompatibilityInline(admin.TabularInline):
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


class TeamInline(ReadOnlyCompatibilityInline):
    model = Team
    fields = ("name", "is_default", "is_active", "created_at")
    readonly_fields = fields


class OrganizationMembershipInline(ReadOnlyCompatibilityInline):
    model = OrganizationMembership
    fields = ("user", "role", "is_active", "invited_by", "joined_at")
    readonly_fields = fields
    verbose_name = "Ancienne appartenance (compatibilité)"
    verbose_name_plural = "Anciennes appartenances (compatibilité)"


class OrganizationFollowInline(ReadOnlyCompatibilityInline):
    model = OrganizationFollow
    readonly_fields = (
        "user",
        "notify_new_events",
        "notify_announcements",
        "email_new_events",
        "email_announcements",
        "followed_at",
        "updated_at",
    )


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "verification_status", "public_profile", "created_by", "created_at")
    list_filter = ("verification_status", "public_profile", "created_at")
    search_fields = ("name", "slug", "contact_email", "created_by__email")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [TeamInline, OrganizationMembershipInline, OrganizationFollowInline]


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "is_default", "is_active", "created_at")
    list_filter = ("is_default", "is_active", "created_at")
    search_fields = ("name", "organization__name", "organization__slug")
    autocomplete_fields = ("organization",)
    readonly_fields = ("organization", "name", "is_default", "is_active", "created_at", "updated_at")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(TeamMembership)
class TeamMembershipAdmin(admin.ModelAdmin):
    list_display = ("team", "user", "status", "invited_by", "joined_at")
    list_filter = ("status", "team__organization", "joined_at")
    search_fields = (
        "team__name",
        "team__organization__name",
        "user__email",
        "user__username",
    )
    list_select_related = ("team", "team__organization", "user", "invited_by")
    readonly_fields = ("team", "user", "status", "invited_by", "joined_at", "created_at", "updated_at")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(OrganizationMembership)
class OrganizationMembershipAdmin(admin.ModelAdmin):
    """Read-only compatibility projection; authority lives in Mandate."""

    list_display = ("organization", "user", "role", "is_active", "joined_at")
    list_filter = ("role", "is_active", "joined_at")
    search_fields = ("organization__name", "user__email", "user__username")
    list_select_related = ("organization", "user", "invited_by")
    readonly_fields = ("organization", "user", "role", "is_active", "invited_by", "joined_at", "updated_at")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(OrganizationFollow)
class OrganizationFollowAdmin(admin.ModelAdmin):
    list_display = ("organization", "user", "notify_new_events", "email_new_events", "notify_announcements", "email_announcements", "followed_at")
    list_filter = ("notify_new_events", "email_new_events", "notify_announcements", "email_announcements", "followed_at")
    search_fields = ("organization__name", "user__email", "user__username")
    autocomplete_fields = ("organization", "user")
    readonly_fields = ("followed_at", "updated_at")
