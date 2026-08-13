from django.contrib import admin

from .models import Activity, Occurrence, OccurrencePlace


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ("title", "space", "status", "visibility", "created_by", "created_at", "updated_at")
    list_filter = ("status", "visibility", "space")
    search_fields = ("title", "slug", "space__name", "created_by__email")
    list_select_related = ("space", "created_by")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Occurrence)
class OccurrenceAdmin(admin.ModelAdmin):
    list_display = ("activity", "start_at", "end_at", "timezone", "status")
    list_filter = ("status", "timezone")
    search_fields = ("activity__title", "label", "activity__space__name")
    list_select_related = ("activity", "activity__space")
    date_hierarchy = "start_at"


@admin.register(OccurrencePlace)
class OccurrencePlaceAdmin(admin.ModelAdmin):
    list_display = ("occurrence", "place", "role", "position")
    list_filter = ("role",)
    search_fields = ("occurrence__activity__title", "place__name", "place__locality")
    list_select_related = ("occurrence", "occurrence__activity", "place")
