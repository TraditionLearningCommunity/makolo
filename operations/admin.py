from django.contrib import admin

from .models import ModerationCase, OperationsAuditLog, OperationsIncident, WorkerHeartbeat


@admin.register(OperationsIncident)
class OperationsIncidentAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "severity", "status", "organization", "event", "assigned_to", "created_at")
    list_filter = ("category", "severity", "status", "created_at")
    search_fields = ("title", "description", "resolution", "organization__name", "event__title")
    autocomplete_fields = ("organization", "event", "payment", "scan_log", "opened_by", "assigned_to")
    readonly_fields = ("created_at", "updated_at", "acknowledged_at", "resolved_at")


@admin.register(ModerationCase)
class ModerationCaseAdmin(admin.ModelAdmin):
    list_display = ("target_type", "organization", "event", "severity", "status", "assigned_to", "created_at")
    list_filter = ("target_type", "severity", "status", "created_at")
    search_fields = ("reason", "outcome", "organization__name", "event__title")
    autocomplete_fields = ("organization", "event", "opened_by", "assigned_to")
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
