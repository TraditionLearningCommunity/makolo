from django.contrib import admin

from .models import Organization, OrganizationMembership


class OrganizationMembershipInline(admin.TabularInline):
    model = OrganizationMembership
    extra = 0
    autocomplete_fields = ("user", "invited_by")


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "verification_status", "public_profile", "created_by", "created_at")
    list_filter = ("verification_status", "public_profile", "created_at")
    search_fields = ("name", "slug", "contact_email", "created_by__email")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [OrganizationMembershipInline]


@admin.register(OrganizationMembership)
class OrganizationMembershipAdmin(admin.ModelAdmin):
    list_display = ("organization", "user", "role", "is_active", "joined_at")
    list_filter = ("role", "is_active", "joined_at")
    search_fields = ("organization__name", "user__email", "user__username")
    autocomplete_fields = ("organization", "user", "invited_by")
