from django import forms
from django.contrib import admin

from .emergency_controls import set_operational_control
from .models import (
    ModerationCase,
    OperationalControl,
    OperationsAuditLog,
    OperationsIncident,
    PlacementAssignment,
    PlacementPlan,
    PlacementUnit,
    WorkerHeartbeat,
)
from .permissions import user_can_access_operations


class OperationalControlAdminForm(forms.ModelForm):
    reason = forms.CharField(
        required=True,
        label="Justification Operations",
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Obligatoire à chaque activation ou désactivation; cette justification est auditée.",
    )

    class Meta:
        model = OperationalControl
        fields = ("is_enabled", "reason", "incident")


@admin.register(OperationalControl)
class OperationalControlAdmin(admin.ModelAdmin):
    form = OperationalControlAdminForm
    list_display = ("code", "is_enabled", "incident", "changed_by", "changed_at")
    list_filter = ("is_enabled",)
    search_fields = ("code", "reason")
    fields = ("code", "is_enabled", "reason", "incident", "changed_by", "changed_at")
    readonly_fields = ("code", "changed_by", "changed_at")
    raw_id_fields = ("incident",)

    def has_module_permission(self, request):
        return user_can_access_operations(request.user)

    def has_view_permission(self, request, obj=None):
        return user_can_access_operations(request.user)

    def has_change_permission(self, request, obj=None):
        return user_can_access_operations(request.user)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        saved = set_operational_control(
            code=obj.code,
            enabled=obj.is_enabled,
            actor=request.user,
            reason=obj.reason,
            incident=obj.incident,
        )
        obj.is_enabled = saved.is_enabled
        obj.reason = saved.reason
        obj.incident_id = saved.incident_id
        obj.changed_by_id = saved.changed_by_id
        obj.changed_at = saved.changed_at


@admin.register(OperationsIncident)
class OperationsIncidentAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "category",
        "severity",
        "status",
        "organization",
        "activity",
        "occurrence",
        "event",
        "assigned_to",
        "created_at",
    )
    list_filter = ("category", "severity", "status", "created_at")
    search_fields = (
        "title",
        "description",
        "resolution",
        "organization__name",
        "activity__title",
        "event__title",
    )
    raw_id_fields = (
        "organization",
        "activity",
        "occurrence",
        "event",
        "payment",
        "scan_log",
        "opened_by",
        "assigned_to",
    )
    readonly_fields = ("created_at", "updated_at", "acknowledged_at", "resolved_at")
    list_select_related = ("organization", "activity", "occurrence", "event", "assigned_to")


@admin.register(PlacementPlan)
class PlacementPlanAdmin(admin.ModelAdmin):
    list_display = ("label", "key", "occurrence", "required", "active", "updated_at")
    list_filter = ("required", "active")
    search_fields = ("label", "key", "occurrence__label", "occurrence__activity__title")
    raw_id_fields = ("occurrence",)


@admin.register(PlacementUnit)
class PlacementUnitAdmin(admin.ModelAdmin):
    list_display = ("label", "key", "plan", "kind", "parent", "exclusive", "active", "position")
    list_filter = ("exclusive", "active", "kind")
    search_fields = ("label", "key", "plan__label", "plan__occurrence__activity__title")
    raw_id_fields = ("plan", "parent")


@admin.register(PlacementAssignment)
class PlacementAssignmentAdmin(admin.ModelAdmin):
    list_display = ("plan", "unit", "beneficiary_display_name", "assigned_by", "assigned_at", "ended_at")
    list_filter = ("plan", "ended_at")
    search_fields = (
        "unit__label",
        "profile__username",
        "profile__first_name",
        "profile__last_name",
        "external_beneficiary__display_name",
    )
    raw_id_fields = ("plan", "unit", "profile", "external_beneficiary", "assigned_by")
    readonly_fields = ("assigned_at", "ended_at")


@admin.register(ModerationCase)
class ModerationCaseAdmin(admin.ModelAdmin):
    list_display = ("target_type", "organization", "event", "severity", "status", "assigned_to", "created_at")
    list_filter = ("target_type", "severity", "status", "created_at")
    search_fields = ("reason", "outcome", "organization__name", "event__title")
    raw_id_fields = ("organization", "event", "opened_by", "assigned_to")
    readonly_fields = ("closed_at", "created_at", "updated_at")


@admin.register(OperationsAuditLog)
class OperationsAuditLogAdmin(admin.ModelAdmin):
    list_display = ("action", "target_type", "target_id", "actor", "created_at")
    list_filter = ("target_type", "action", "created_at")
    search_fields = ("action", "target_type", "target_id", "summary")
    readonly_fields = (
        "actor",
        "action",
        "target_type",
        "target_id",
        "summary",
        "before",
        "after",
        "metadata",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(WorkerHeartbeat)
class WorkerHeartbeatAdmin(admin.ModelAdmin):
    list_display = ("worker_name", "instance_id", "state", "last_seen_at", "last_cycle_finished_at")
    list_filter = ("state", "worker_name")
    search_fields = ("worker_name", "instance_id", "last_error")
    readonly_fields = (
        "worker_name",
        "instance_id",
        "state",
        "last_seen_at",
        "last_cycle_started_at",
        "last_cycle_finished_at",
        "last_error",
        "metadata",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
