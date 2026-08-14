from django.contrib import admin

from .models import CapacityPool, CapacityReservation
from .selectors import capacity_availability


@admin.register(CapacityPool)
class CapacityPoolAdmin(admin.ModelAdmin):
    list_display = ("label", "activity", "occurrence", "total_quantity", "available_display", "is_active")
    list_filter = ("is_active", "activity")
    search_fields = ("label", "activity__title", "source_key")
    list_select_related = ("activity", "occurrence")
    readonly_fields = ("created_at", "updated_at", "available_display")

    @admin.display(description="Disponible")
    def available_display(self, obj):
        value = capacity_availability(obj).available
        return "Illimité" if value is None else value


@admin.register(CapacityReservation)
class CapacityReservationAdmin(admin.ModelAdmin):
    list_display = ("pool", "journey", "quantity", "status", "expires_at", "committed_at")
    list_filter = ("status", "pool__activity")
    search_fields = ("source_key", "journey__beneficiary__email", "pool__label")
    list_select_related = ("pool", "pool__activity", "journey", "journey__beneficiary")
    readonly_fields = (
        "pool",
        "journey",
        "quantity",
        "status",
        "expires_at",
        "committed_at",
        "released_at",
        "expired_at",
        "source_key",
        "created_at",
        "updated_at",
    )
