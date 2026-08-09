from django.contrib import admin

from .models import EventBookmark


@admin.register(EventBookmark)
class EventBookmarkAdmin(admin.ModelAdmin):
    list_display = ("user", "event", "created_at")
    search_fields = ("user__email", "event__title")
    raw_id_fields = ("user", "event")
    readonly_fields = ("created_at",)
