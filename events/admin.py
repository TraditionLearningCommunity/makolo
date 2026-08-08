from django.contrib import admin

from .models import Event, EventCategory, EventVenue


@admin.register(EventCategory)
class EventCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(EventVenue)
class EventVenueAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "city", "country", "is_active")
    list_filter = ("kind", "is_active", "country")
    search_fields = ("name", "city", "country", "address")


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("title", "organization", "organizer", "status", "visibility", "start_at", "capacity")
    list_filter = ("status", "visibility", "category", "organization")
    search_fields = ("title", "slug", "organization__name", "organizer__email", "organizer__username")
    autocomplete_fields = ("organization", "organizer")
    readonly_fields = ("slug", "published_at", "cancelled_at", "created_at", "updated_at")
    date_hierarchy = "start_at"
