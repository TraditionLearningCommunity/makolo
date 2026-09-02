from django.contrib import admin

from .models import RequirementReusePolicy


@admin.register(RequirementReusePolicy)
class RequirementReusePolicyAdmin(admin.ModelAdmin):
    list_display = ("requirement", "key", "source_type", "artifact_kind", "proof_type", "human_review_required", "created_at")
    list_filter = ("source_type", "human_review_required", "require_not_expired")
    search_fields = ("key", "requirement__title")
    readonly_fields = ("created_at",)

    def has_change_permission(self, request, obj=None):
        if obj is not None:
            return False
        return super().has_change_permission(request, obj=obj)

    def has_delete_permission(self, request, obj=None):
        if obj is not None and obj.requirement.revision.published_at is not None:
            return False
        return super().has_delete_permission(request, obj=obj)
