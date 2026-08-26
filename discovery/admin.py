from django.contrib import admin

from .models import ActivityBookmark


@admin.register(ActivityBookmark)
class ActivityBookmarkAdmin(admin.ModelAdmin):
    list_display = ("user", "activity", "created_at")
    search_fields = ("user__email", "activity__title")
    raw_id_fields = ("user", "activity")
    readonly_fields = ("created_at",)
