from django.contrib import admin

from .models import Mandate, Permission, Role, RolePermission


class ReadOnlyAuthorityAdminMixin:
    """Authority mutations must go through domain services, not arbitrary admin edits."""

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        return tuple(field.name for field in self.model._meta.fields)


@admin.register(Permission)
class PermissionAdmin(ReadOnlyAuthorityAdminMixin, admin.ModelAdmin):
    list_display = ("code", "name", "domain", "scope_type", "is_active", "is_system")
    list_filter = ("scope_type", "domain", "is_active", "is_system")
    search_fields = ("code", "name", "description", "domain")
    ordering = ("domain", "code")


class RolePermissionInline(admin.TabularInline):
    model = RolePermission
    extra = 0
    can_delete = False
    readonly_fields = ("permission", "created_at")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Role)
class RoleAdmin(ReadOnlyAuthorityAdminMixin, admin.ModelAdmin):
    list_display = ("name", "code", "scope_type", "organization", "is_system", "is_active")
    list_filter = ("scope_type", "is_system", "is_active")
    search_fields = ("name", "code", "description", "organization__name")
    autocomplete_fields = ()
    inlines = [RolePermissionInline]


@admin.register(RolePermission)
class RolePermissionAdmin(ReadOnlyAuthorityAdminMixin, admin.ModelAdmin):
    list_display = ("role", "permission", "created_at")
    list_filter = ("role__scope_type", "permission__domain")
    search_fields = ("role__name", "role__code", "permission__name", "permission__code")
    list_select_related = ("role", "permission")


@admin.register(Mandate)
class MandateAdmin(ReadOnlyAuthorityAdminMixin, admin.ModelAdmin):
    list_display = (
        "profile",
        "role",
        "scope_type",
        "space",
        "group",
        "status",
        "valid_from",
        "valid_until",
        "granted_at",
    )
    list_filter = ("scope_type", "status", "role", "valid_from", "valid_until")
    search_fields = (
        "profile__email",
        "profile__username",
        "role__name",
        "role__code",
        "space__name",
        "space__slug",
        "group__name",
        "group__slug",
        "source",
    )
    list_select_related = ("profile", "role", "space", "group", "granted_by")
    date_hierarchy = "granted_at"
