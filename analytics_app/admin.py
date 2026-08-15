from django.contrib import admin

from .models import AnalyticsFact, GrowthSpend


@admin.register(GrowthSpend)
class GrowthSpendAdmin(admin.ModelAdmin):
    list_display = (
        "organization",
        "channel",
        "label",
        "amount",
        "currency",
        "incurred_at",
        "created_by",
    )
    list_filter = ("channel", "currency", "incurred_at")
    search_fields = ("organization__name", "label", "notes")
    autocomplete_fields = (
        "organization",
        "event",
        "crm_campaign",
        "partner_campaign",
        "promotion",
        "loyalty_program",
        "created_by",
    )
    readonly_fields = ("created_at", "updated_at")


@admin.register(AnalyticsFact)
class AnalyticsFactAdmin(admin.ModelAdmin):
    list_display = (
        "fact_type",
        "space",
        "activity",
        "occurrence",
        "numeric_value",
        "currency",
        "occurred_at",
    )
    list_filter = ("fact_type", "currency", "occurred_at")
    search_fields = ("fact_type", "space__name", "activity__title")
    list_select_related = ("space", "activity", "occurrence", "profile", "domain_event")
    readonly_fields = (
        "domain_event",
        "fact_type",
        "space",
        "activity",
        "occurrence",
        "profile",
        "numeric_value",
        "currency",
        "occurred_at",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
