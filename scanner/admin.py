from django.contrib import admin

from .models import EventAccessGate, ScanLog, ScannerAssignment


@admin.register(EventAccessGate)
class EventAccessGateAdmin(admin.ModelAdmin):
    list_display = (
        "event",
        "name",
        "is_active",
        "throughput_target_per_minute",
        "warning_rejection_rate",
        "priority",
    )
    list_filter = ("is_active", "event")
    search_fields = ("event__title", "name", "slug")
    autocomplete_fields = ("event", "created_by")
    readonly_fields = ("slug", "created_at", "updated_at")


@admin.register(ScannerAssignment)
class ScannerAssignmentAdmin(admin.ModelAdmin):
    list_display = (
        "event",
        "agent",
        "access_gate",
        "label",
        "is_active",
        "valid_from",
        "valid_until",
    )
    list_filter = ("is_active", "event", "access_gate")
    search_fields = (
        "event__title",
        "agent__username",
        "agent__email",
        "access_gate__name",
        "label",
    )
    autocomplete_fields = ("event", "agent", "assigned_by", "access_gate")
    readonly_fields = ("created_at", "updated_at")


@admin.register(ScanLog)
class ScanLogAdmin(admin.ModelAdmin):
    list_display = (
        "scanned_at",
        "event",
        "scanner",
        "result",
        "ticket",
        "access_gate",
        "gate",
    )
    list_filter = ("result", "event", "access_gate", "scanned_at")
    search_fields = (
        "event__title",
        "scanner__username",
        "scanner__email",
        "ticket__code",
        "ticket__holder_name",
        "access_gate__name",
        "client_reference",
        "qr_fingerprint",
    )
    autocomplete_fields = ("event", "ticket", "scanner", "assignment", "access_gate")
    readonly_fields = (
        "event",
        "ticket",
        "scanner",
        "assignment",
        "access_gate",
        "result",
        "message",
        "qr_fingerprint",
        "client_reference",
        "gate",
        "metadata",
        "scanned_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
