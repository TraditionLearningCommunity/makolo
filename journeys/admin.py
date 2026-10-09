from django.contrib import admin

from core.admin_boundaries import TechnicalReadOnlyAdmin

from .models import (
    Journey,
    JourneyArtifact,
    JourneyArtifactReview,
    JourneyAssignment,
    JourneyBlocker,
    JourneyNote,
    JourneyRequest,
    JourneyStep,
    JourneyStepAssignment,
    JourneyStepDependency,
    JourneyTransition,
)


@admin.register(Journey)
class JourneyAdmin(TechnicalReadOnlyAdmin):
    list_display = ("beneficiary", "activity", "occurrence", "workflow", "status", "started_at", "created_at", "updated_at")
    list_filter = ("workflow", "status", "activity")
    search_fields = ("beneficiary__email", "initiated_by__email", "activity__title")
    list_select_related = ("beneficiary", "initiated_by", "activity", "occurrence")
    readonly_fields = ("status", "submitted_at", "confirmed_at", "started_at", "fulfilled_at", "cancelled_at", "created_at", "updated_at")


@admin.register(JourneyRequest)
class JourneyRequestAdmin(TechnicalReadOnlyAdmin):
    list_display = ("journey", "status", "purpose", "requester", "decided_by", "submitted_at", "decided_at")
    list_filter = ("status", "purpose")
    search_fields = ("journey__activity__title", "requester__email", "decided_by__email")
    list_select_related = ("journey", "requester", "decided_by")
    readonly_fields = ("status", "submitted_at", "decided_at", "created_at", "updated_at")


@admin.register(JourneyTransition)
class JourneyTransitionAdmin(TechnicalReadOnlyAdmin):
    list_display = ("journey", "from_status", "to_status", "actor", "reason", "created_at")
    list_filter = ("from_status", "to_status")
    search_fields = ("journey__activity__title", "actor__email", "reason")
    list_select_related = ("journey", "actor")
    readonly_fields = ("journey", "from_status", "to_status", "actor", "reason", "created_at")


@admin.register(JourneyStep)
class JourneyStepAdmin(TechnicalReadOnlyAdmin):
    list_display = ("journey", "position", "kind", "title", "status", "is_required", "due_at")
    list_filter = ("kind", "status", "is_required", "origin")
    readonly_fields = ("status", "started_at", "completed_at", "skipped_at", "cancelled_at", "status_changed_by", "status_reason", "created_at", "updated_at")


@admin.register(JourneyStepDependency)
class JourneyStepDependencyAdmin(TechnicalReadOnlyAdmin):
    list_display = ("step", "depends_on", "created_at")
    readonly_fields = ("step", "depends_on", "created_at")


@admin.register(JourneyBlocker)
class JourneyBlockerAdmin(TechnicalReadOnlyAdmin):
    list_display = ("journey", "step", "severity", "category", "title", "status", "detected_at", "resolved_at")
    list_filter = ("status", "severity", "category")
    readonly_fields = ("status", "detected_at", "resolved_by", "resolved_at", "resolution_note", "created_at", "updated_at")


@admin.register(JourneyAssignment)
class JourneyAssignmentAdmin(TechnicalReadOnlyAdmin):
    list_display = ("journey", "profile", "responsibility", "is_primary", "status", "assigned_at", "ended_at")
    list_filter = ("status", "responsibility", "is_primary")
    readonly_fields = ("status", "assigned_at", "ended_at", "created_at", "updated_at")


@admin.register(JourneyStepAssignment)
class JourneyStepAssignmentAdmin(TechnicalReadOnlyAdmin):
    list_display = ("step", "profile", "responsibility", "status", "assigned_at", "ended_at")
    list_filter = ("status", "responsibility")
    readonly_fields = ("status", "assigned_at", "ended_at", "created_at", "updated_at")


@admin.register(JourneyArtifact)
class JourneyArtifactAdmin(TechnicalReadOnlyAdmin):
    list_display = ("journey", "step", "kind", "title", "version", "status", "sensitivity", "uploaded_at")
    list_filter = ("kind", "status", "sensitivity")
    readonly_fields = ("file", "status", "supersedes", "version", "uploaded_by", "uploaded_at", "size", "mime_type", "content_hash", "created_at", "updated_at")
    exclude = ("file",)

    def has_module_permission(self, request):
        return bool(request.user.is_authenticated and request.user.is_active and request.user.is_staff and request.user.is_superuser)

    def has_view_permission(self, request, obj=None):
        return bool(request.user.is_authenticated and request.user.is_active and request.user.is_staff and request.user.is_superuser)

    def get_fields(self, request, obj=None):
        return tuple(field for field in super().get_fields(request, obj) if field != "file")


@admin.register(JourneyArtifactReview)
class JourneyArtifactReviewAdmin(TechnicalReadOnlyAdmin):
    list_display = ("artifact", "reviewer", "status", "requested_at", "decided_at")
    list_filter = ("status",)
    readonly_fields = ("artifact", "reviewer", "requested_by", "status", "comment", "requested_at", "started_at", "decided_at", "created_at", "updated_at")


@admin.register(JourneyNote)
class JourneyNoteAdmin(TechnicalReadOnlyAdmin):
    list_display = ("journey", "step", "author", "visibility", "created_at")
    list_filter = ("visibility",)
    readonly_fields = ("journey", "step", "author", "visibility", "body", "created_at", "updated_at")
