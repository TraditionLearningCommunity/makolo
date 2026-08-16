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
    list_display = ("name", "kind", "place", "effective_city", "is_active")
    list_filter = ("kind", "is_active", "place__country_code")
    search_fields = ("name", "place__name", "place__locality", "place__address_line")
    autocomplete_fields = ("place",)
    readonly_fields = ("address", "city", "country", "latitude", "longitude", "created_at", "updated_at")


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = (
        "display_title",
        "display_space",
        "display_status",
        "display_visibility",
        "display_occurrence",
        "display_place",
    )
    list_filter = ("activity__status", "activity__visibility", "category", "activity__space")
    search_fields = (
        "activity__title",
        "slug",
        "activity__space__name",
        "activity__created_by__email",
        "activity__created_by__username",
    )
    readonly_fields = (
        "activity",
        "slug",
        "primary_occurrence_display",
        "primary_place_display",
        "published_at",
        "cancelled_at",
        "created_at",
        "updated_at",
    )

    @admin.display(description="Événement", ordering="activity__title")
    def display_title(self, obj):
        return obj.title

    @admin.display(description="Espace", ordering="activity__space__name")
    def display_space(self, obj):
        return obj.organization

    @admin.display(description="Statut", ordering="activity__status")
    def display_status(self, obj):
        return obj.status

    @admin.display(description="Visibilité", ordering="activity__visibility")
    def display_visibility(self, obj):
        return obj.visibility

    @admin.display(description="Occurrence")
    def display_occurrence(self, obj):
        return obj.primary_occurrence

    @admin.display(description="Lieu")
    def display_place(self, obj):
        return obj.primary_place

    def primary_occurrence_display(self, obj):
        return obj.primary_occurrence

    primary_occurrence_display.short_description = "Occurrence principale"

    def primary_place_display(self, obj):
        return obj.primary_place

    primary_place_display.short_description = "Place canonique"
