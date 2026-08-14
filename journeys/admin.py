from django.contrib import admin

from .models import Journey, JourneyRequest, JourneyTransition


@admin.register(Journey)
class JourneyAdmin(admin.ModelAdmin):
    list_display = (
        "beneficiary",
        "activity",
        "occurrence",
        "workflow",
        "status",
        "created_at",
        "updated_at",
    )
    list_filter = ("workflow", "status", "activity")
    search_fields = ("beneficiary__email", "initiated_by__email", "activity__title")
    list_select_related = ("beneficiary", "initiated_by", "activity", "occurrence")
    readonly_fields = ("created_at", "updated_at")


@admin.register(JourneyRequest)
class JourneyRequestAdmin(admin.ModelAdmin):
    list_display = ("journey", "status", "purpose", "requester", "decided_by", "submitted_at", "decided_at")
    list_filter = ("status", "purpose")
    search_fields = ("journey__activity__title", "requester__email", "decided_by__email")
    list_select_related = ("journey", "requester", "decided_by")
    readonly_fields = ("submitted_at", "decided_at", "created_at", "updated_at")


@admin.register(JourneyTransition)
class JourneyTransitionAdmin(admin.ModelAdmin):
    list_display = ("journey", "from_status", "to_status", "actor", "reason", "created_at")
    list_filter = ("from_status", "to_status")
    search_fields = ("journey__activity__title", "actor__email", "reason")
    list_select_related = ("journey", "actor")
    readonly_fields = ("journey", "from_status", "to_status", "actor", "reason", "created_at")
