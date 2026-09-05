from django.contrib import admin

from .models import Access, AccessCredential, AccessUse


class ReadOnlyAccessAdminMixin:
    """Access rights and credentials must transition through domain services."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        return tuple(field.name for field in self.model._meta.fields)


@admin.register(Access)
class AccessAdmin(ReadOnlyAccessAdminMixin, admin.ModelAdmin):
    list_display = ("beneficiary", "activity", "occurrence", "status", "valid_from", "valid_until", "journey")
    list_filter = ("status", "single_use", "activity")
    search_fields = ("beneficiary__email", "activity__title", "source_key")
    list_select_related = ("beneficiary", "activity", "occurrence", "journey")


@admin.register(AccessCredential)
class AccessCredentialAdmin(ReadOnlyAccessAdminMixin, admin.ModelAdmin):
    list_display = ("access", "credential_type", "status", "version", "issued_at", "revoked_at", "expired_at")
    list_filter = ("credential_type", "status")
    search_fields = ("access__beneficiary__email", "access__activity__title", "public_id")
    list_select_related = ("access", "access__beneficiary", "access__activity")


@admin.register(AccessUse)
class AccessUseAdmin(ReadOnlyAccessAdminMixin, admin.ModelAdmin):
    list_display = ("result", "access", "occurrence", "actor", "source", "used_at")
    list_filter = ("result", "source")
    search_fields = ("access__beneficiary__email", "access__activity__title", "actor__email")
    list_select_related = ("access", "occurrence", "actor", "credential")
