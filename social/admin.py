from django.contrib import admin

from .models import Contribution


@admin.register(Contribution)
class ContributionAdmin(admin.ModelAdmin):
    list_display = ("kind", "author_profile", "group", "activity", "visibility", "status", "created_at")
    list_filter = ("kind", "visibility", "status")
    search_fields = ("author_profile__email", "author_profile__username", "body")
    readonly_fields = ("created_at", "updated_at", "edited_at", "moderated_at")
