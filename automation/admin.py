from django.contrib import admin

from .models import (
    AutomationExecution,
    AutomationRule,
    AutomationRun,
    CRMWorkflow,
    CRMWorkflowAction,
    CRMWorkflowActionRun,
    CRMWorkflowRun,
    EventAutomationPolicy,
)


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


@admin.register(AutomationRule)
class AutomationRuleAdmin(admin.ModelAdmin):
    list_display = ("name", "space", "activity", "trigger_event_type", "action_kind", "is_active", "updated_at")
    list_filter = ("space", "is_active", "trigger_event_type", "action_kind")
    search_fields = ("name", "space__name", "activity__title", "trigger_event_type")
    autocomplete_fields = ("space", "activity", "created_by")


@admin.register(AutomationExecution)
class AutomationExecutionAdmin(admin.ModelAdmin):
    list_display = ("rule", "domain_event", "action", "status", "attempts", "created_at", "completed_at")
    list_filter = ("status", "action", "rule__space")
    search_fields = ("rule__name", "domain_event__event_type", "domain_event__id")
    readonly_fields = [field.name for field in AutomationExecution._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class CRMWorkflowActionInline(admin.TabularInline):
    model = CRMWorkflowAction
    extra = 0
    fields = ("position", "kind", "delay_minutes", "template", "tag", "title", "is_active")


@admin.register(CRMWorkflow)
class CRMWorkflowAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "trigger", "event", "is_active", "updated_at")
    list_filter = ("organization", "trigger", "is_active")
    search_fields = ("name", "description", "organization__name", "event__title")
    autocomplete_fields = ("organization", "event", "segment", "ticket_type", "created_by")
    inlines = [CRMWorkflowActionInline]


@admin.register(CRMWorkflowAction)
class CRMWorkflowActionAdmin(admin.ModelAdmin):
    list_display = ("workflow", "position", "kind", "delay_minutes", "is_active")
    list_filter = ("kind", "is_active", "workflow__organization")
    search_fields = ("workflow__name", "title", "message")
    autocomplete_fields = ("workflow", "template", "tag")


@admin.register(CRMWorkflowRun)
class CRMWorkflowRunAdmin(admin.ModelAdmin):
    list_display = ("workflow", "contact", "event", "source_type", "status", "created_at", "completed_at")
    list_filter = ("status", "source_type", "workflow__organization")
    search_fields = ("dedup_key", "source_id", "contact__email", "workflow__name")
    readonly_fields = [field.name for field in CRMWorkflowRun._meta.fields]

    def has_add_permission(self, request):
        return False


@admin.register(CRMWorkflowActionRun)
class CRMWorkflowActionRunAdmin(admin.ModelAdmin):
    list_display = ("run", "action", "status", "attempts", "scheduled_for", "completed_at")
    list_filter = ("status", "action__kind", "run__workflow__organization")
    search_fields = ("run__dedup_key", "run__contact__email", "action__workflow__name")
    readonly_fields = [field.name for field in CRMWorkflowActionRun._meta.fields]

    def has_add_permission(self, request):
        return False
