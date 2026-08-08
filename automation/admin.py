from django.contrib import admin

from .models import AutomationRun, EventAutomationPolicy


@admin.register(EventAutomationPolicy)
class EventAutomationPolicyAdmin(admin.ModelAdmin):
    list_display = ("event", "is_active", "reminder_24h_enabled", "reminder_2h_enabled", "auto_complete_event", "updated_at")
    list_filter = ("is_active", "reminder_7d_enabled", "reminder_24h_enabled", "reminder_2h_enabled", "auto_complete_event")
    search_fields = ("event__title", "event__slug")
    autocomplete_fields = ("event",)


@admin.register(AutomationRun)
class AutomationRunAdmin(admin.ModelAdmin):
    list_display = ("rule_key", "event", "status", "summary", "created_at")
    list_filter = ("rule_key", "status", "created_at")
    search_fields = ("dedup_key", "summary", "event__title")
    readonly_fields = [field.name for field in AutomationRun._meta.fields]

    def has_add_permission(self, request):
        return False
