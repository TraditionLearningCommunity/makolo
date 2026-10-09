from django.contrib import admin

from core.admin_boundaries import TechnicalReadOnlyAdmin

from .models import Activity, Occurrence, OccurrencePlace


@admin.register(Activity)
class ActivityAdmin(TechnicalReadOnlyAdmin):
    list_display = ("title", "space", "status", "visibility", "created_by", "created_at", "updated_at")
    list_filter = ("status", "visibility", "space")
    search_fields = ("title", "slug", "space__name", "created_by__email")
    list_select_related = ("space", "created_by")
    readonly_fields = ("status", "visibility", "created_at", "updated_at")

    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)
        # Only the owner workflow can transfer responsibility or authority.
        return (*fields, "space", "owner_profile", "created_by") if obj else fields

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Occurrence)
class OccurrenceAdmin(TechnicalReadOnlyAdmin):
    list_display = ("activity", "start_at", "end_at", "timezone", "status")
    list_filter = ("status", "timezone")
    search_fields = ("activity__title", "label", "activity__space__name")
    list_select_related = ("activity", "activity__space")
    date_hierarchy = "start_at"
    readonly_fields = ("status", "schedule", "schedule_local_date", "created_at", "updated_at")

    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)
        return (*fields, "activity") if obj else fields

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(OccurrencePlace)
class OccurrencePlaceAdmin(TechnicalReadOnlyAdmin):
    list_display = ("occurrence", "place", "role", "position")
    list_filter = ("role",)
    search_fields = ("occurrence__activity__title", "place__name", "place__locality")
    list_select_related = ("occurrence", "occurrence__activity", "place")

    def has_delete_permission(self, request, obj=None):
        return False
