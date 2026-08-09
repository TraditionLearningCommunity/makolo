from django.contrib import admin

from .models import GrowthSpend


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
