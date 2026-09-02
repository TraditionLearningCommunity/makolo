from django.contrib import admin

from .models import RequirementReuseApplication, RequirementReusePolicy


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


@admin.register(RequirementReuseApplication)
class RequirementReuseApplicationAdmin(admin.ModelAdmin):
    list_display = ("assessment", "source_type", "policy", "decision", "applied_by", "applied_at")
    list_filter = ("source_type", "decision", "confirmation_confirmed")
    search_fields = ("policy__key",)
    readonly_fields = [field.name for field in RequirementReuseApplication._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
