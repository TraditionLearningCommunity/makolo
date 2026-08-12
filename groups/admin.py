from django.contrib import admin

from .models import (
    Group,
    GroupInvitation,
    GroupMembership,
    GroupSnapshot,
    GroupSnapshotMember,
)


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ("name", "status", "visibility", "space", "owner_profile", "created_at")
    list_filter = ("status", "visibility", "created_at")
    search_fields = ("name", "slug", "description", "space__name", "owner_profile__email")
    readonly_fields = ("space", "owner_profile", "created_by", "created_at", "updated_at")

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(GroupMembership)
class GroupMembershipAdmin(admin.ModelAdmin):
    list_display = ("group", "profile", "status", "source", "external_reference", "joined_at")
    list_filter = ("status", "source", "joined_at")
    search_fields = ("group__name", "profile__email", "profile__first_name", "profile__last_name", "external_reference")
    readonly_fields = (
        "group",
        "profile",
        "status",
        "source",
        "joined_at",
        "verified_at",
        "external_reference",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(GroupInvitation)
class GroupInvitationAdmin(admin.ModelAdmin):
    list_display = ("group", "profile", "email", "phone", "status", "expires_at", "created_at")
    list_filter = ("status", "expires_at", "created_at")
    search_fields = ("group__name", "profile__email", "email", "phone", "external_reference")
    readonly_fields = (
        "group",
        "profile",
        "email",
        "phone",
        "external_reference",
        "first_name",
        "last_name",
        "invited_by",
        "status",
        "expires_at",
        "token_digest",
        "accepted_at",
        "rejected_at",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(GroupSnapshot)
class GroupSnapshotAdmin(admin.ModelAdmin):
    list_display = ("group", "name", "member_count", "created_by", "created_at")
    list_filter = ("created_at",)
    search_fields = ("group__name", "name", "created_by__email")
    readonly_fields = ("group", "name", "member_count", "created_by", "created_at")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(GroupSnapshotMember)
class GroupSnapshotMemberAdmin(admin.ModelAdmin):
    list_display = ("snapshot", "profile", "external_reference", "joined_at")
    list_filter = ("created_at",)
    search_fields = ("snapshot__name", "snapshot__group__name", "profile__email", "external_reference")
    readonly_fields = ("snapshot", "profile", "external_reference", "joined_at", "created_at")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
