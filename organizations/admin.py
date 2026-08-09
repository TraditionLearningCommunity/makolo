from django.contrib import admin

from .models import Organization, OrganizationFollow, OrganizationMembership


class OrganizationMembershipInline(admin.TabularInline):
    model = OrganizationMembership
    extra = 0
    autocomplete_fields = ("user", "invited_by")


class OrganizationFollowInline(admin.TabularInline):
    model = OrganizationFollow
    extra = 0
    can_delete = False
    readonly_fields = ("user", "notify_new_events", "notify_announcements", "email_new_events", "email_announcements", "followed_at", "updated_at")


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "verification_status", "public_profile", "created_by", "created_at")
    list_filter = ("verification_status", "public_profile", "created_at")
    search_fields = ("name", "slug", "contact_email", "created_by__email")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [OrganizationMembershipInline, OrganizationFollowInline]


@admin.register(OrganizationMembership)
class OrganizationMembershipAdmin(admin.ModelAdmin):
    list_display = ("organization", "user", "role", "is_active", "joined_at")
    list_filter = ("role", "is_active", "joined_at")
    search_fields = ("organization__name", "user__email", "user__username")
    autocomplete_fields = ("organization", "user", "invited_by")


@admin.register(OrganizationFollow)
class OrganizationFollowAdmin(admin.ModelAdmin):
    list_display = ("organization", "user", "notify_new_events", "email_new_events", "notify_announcements", "email_announcements", "followed_at")
    list_filter = ("notify_new_events", "email_new_events", "notify_announcements", "email_announcements", "followed_at")
    search_fields = ("organization__name", "user__email", "user__username")
    autocomplete_fields = ("organization", "user")
    readonly_fields = ("followed_at", "updated_at")
