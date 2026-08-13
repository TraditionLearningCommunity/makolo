from django.contrib import admin

from .models import Place, SpacePlace, Zone


@admin.register(Place)
class PlaceAdmin(admin.ModelAdmin):
    list_display = ("name", "locality", "country_code", "latitude", "longitude", "is_active", "created_by")
    list_filter = ("country_code", "is_active")
    search_fields = ("name", "address_line", "locality", "administrative_area")
    autocomplete_fields = ("created_by",)


@admin.register(Zone)
class ZoneAdmin(admin.ModelAdmin):
    list_display = ("name", "zone_type", "country_code", "radius_m", "is_active")
    list_filter = ("zone_type", "country_code", "is_active")
    search_fields = ("name", "locality", "administrative_area")
    autocomplete_fields = ("center_place", "created_by")


@admin.register(SpacePlace)
class SpacePlaceAdmin(admin.ModelAdmin):
    list_display = ("organization", "place", "role", "is_primary", "is_public", "is_active")
    list_filter = ("role", "is_primary", "is_public", "is_active")
    search_fields = ("organization__name", "place__name", "place__locality")
    autocomplete_fields = ("organization", "place")
