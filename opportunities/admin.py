from django.contrib import admin

from .models import (
    Opportunity,
    OpportunityRequirement,
    OpportunityRevision,
    OpportunitySave,
    OpportunitySource,
    OpportunitySourceCheck,
    OpportunitySubmission,
    OpportunityZone,
)


@admin.register(Opportunity)
class OpportunityAdmin(admin.ModelAdmin):
    list_display = ("id", "kind", "publication_status", "current_revision", "published_at")
    list_filter = ("kind", "publication_status")
    readonly_fields = ("publication_status", "current_revision", "merged_into", "published_at", "created_at", "updated_at")


@admin.register(OpportunityRevision)
class OpportunityRevisionAdmin(admin.ModelAdmin):
    list_display = ("opportunity", "version", "title", "issuer_name", "published_at", "deadline_at")
    list_filter = ("published_at",)
    search_fields = ("title", "issuer_name")
    readonly_fields = ("published_at", "created_at")

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        if obj and obj.published_at:
            fields.extend(["opportunity", "version", "title", "summary", "issuer_name", "opens_at", "deadline_at", "timezone", "application_instructions", "remote_allowed", "change_summary", "created_by"])
        return tuple(dict.fromkeys(fields))

    def has_delete_permission(self, request, obj=None):
        if obj and obj.published_at:
            return False
        return super().has_delete_permission(request, obj)


@admin.register(OpportunitySource)
class OpportunitySourceAdmin(admin.ModelAdmin):
    list_display = ("opportunity", "source_type", "source_name", "is_primary", "status", "last_checked_at")
    list_filter = ("source_type", "status", "is_primary")
    readonly_fields = ("status", "last_checked_at", "verified_at", "verified_by", "created_at", "updated_at")


@admin.register(OpportunitySourceCheck)
class OpportunitySourceCheckAdmin(admin.ModelAdmin):
    list_display = ("source", "result", "checked_at", "checked_by")
    list_filter = ("result",)
    readonly_fields = ("source", "result", "checked_at", "checked_by", "fingerprint", "note", "created_at")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(OpportunityRequirement)
class OpportunityRequirementAdmin(admin.ModelAdmin):
    list_display = ("revision", "position", "kind", "title", "is_mandatory")
    list_filter = ("kind", "is_mandatory")


@admin.register(OpportunityZone)
class OpportunityZoneAdmin(admin.ModelAdmin):
    list_display = ("revision", "zone", "role", "created_at")
    list_filter = ("role",)


@admin.register(OpportunitySave)
class OpportunitySaveAdmin(admin.ModelAdmin):
    list_display = ("profile", "opportunity", "created_at")
    readonly_fields = ("profile", "opportunity", "created_at")


@admin.register(OpportunitySubmission)
class OpportunitySubmissionAdmin(admin.ModelAdmin):
    list_display = ("submitted_by", "status", "url", "reviewed_by", "reviewed_at", "created_at")
    list_filter = ("status",)
    readonly_fields = ("status", "reviewed_by", "reviewed_at", "resolved_opportunity", "created_at", "updated_at")
