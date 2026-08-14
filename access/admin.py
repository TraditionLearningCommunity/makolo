from django.contrib import admin

from .models import Access, AccessCredential, AccessUse


@admin.register(Access)
class AccessAdmin(admin.ModelAdmin):
    list_display = ("beneficiary", "activity", "occurrence", "status", "valid_from", "valid_until", "journey")
    list_filter = ("status", "single_use", "activity")
    search_fields = ("beneficiary__email", "activity__title", "source_key")
    list_select_related = ("beneficiary", "activity", "occurrence", "journey")
    readonly_fields = ("created_at", "updated_at")


@admin.register(AccessCredential)
class AccessCredentialAdmin(admin.ModelAdmin):
    list_display = ("access", "credential_type", "status", "version", "issued_at", "revoked_at", "expired_at")
    list_filter = ("credential_type", "status")
    search_fields = ("access__beneficiary__email", "access__activity__title", "public_id")
    list_select_related = ("access", "access__beneficiary", "access__activity")
    readonly_fields = ("public_id", "version", "issued_at", "revoked_at", "expired_at", "created_at", "updated_at")


@admin.register(AccessUse)
class AccessUseAdmin(admin.ModelAdmin):
    list_display = ("result", "access", "occurrence", "actor", "source", "used_at")
    list_filter = ("result", "source")
    search_fields = ("access__beneficiary__email", "access__activity__title", "actor__email")
    list_select_related = ("access", "occurrence", "actor", "credential")
    readonly_fields = ("access", "credential", "actor", "occurrence", "result", "source", "used_at", "created_at")
