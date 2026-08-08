from django.contrib import admin

from .models import ScanLog, ScannerAssignment


@admin.register(ScannerAssignment)
class ScannerAssignmentAdmin(admin.ModelAdmin):
    list_display = (
        "event",
        "agent",
        "label",
        "is_active",
        "valid_from",
        "valid_until",
    )
    list_filter = ("is_active", "event")
    search_fields = (
        "event__title",
        "agent__username",
        "agent__email",
        "label",
    )
    autocomplete_fields = ("event", "agent", "assigned_by")
    readonly_fields = ("created_at", "updated_at")


@admin.register(ScanLog)
class ScanLogAdmin(admin.ModelAdmin):
    list_display = (
        "scanned_at",
        "event",
        "scanner",
        "result",
        "ticket",
        "gate",
    )
    list_filter = ("result", "event", "scanned_at")
    search_fields = (
        "event__title",
        "scanner__username",
        "scanner__email",
        "ticket__code",
        "ticket__holder_name",
        "client_reference",
        "qr_fingerprint",
    )
    autocomplete_fields = ("event", "ticket", "scanner", "assignment")
    readonly_fields = (
        "event",
        "ticket",
        "scanner",
        "assignment",
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
