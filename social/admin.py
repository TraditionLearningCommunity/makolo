from django.contrib import admin

from .models import ActionNeed, Contribution, ProfileSolicitation


@admin.register(Contribution)
class ContributionAdmin(admin.ModelAdmin):
    list_display = ("kind", "author_profile", "group", "activity", "visibility", "status", "created_at")
    list_filter = ("kind", "visibility", "status")
    search_fields = ("author_profile__email", "author_profile__username", "body")
    readonly_fields = ("created_at", "updated_at", "edited_at", "moderated_at")


@admin.register(ActionNeed)
class ActionNeedAdmin(admin.ModelAdmin):
    list_display = ("title", "owner_profile", "space", "open_to_kind", "status", "created_by", "created_at")
    list_filter = ("status", "open_to_kind")
    search_fields = ("title", "description", "owner_profile__username", "space__name")
    readonly_fields = ("created_at", "updated_at")


@admin.register(ProfileSolicitation)
class ProfileSolicitationAdmin(admin.ModelAdmin):
    list_display = ("need", "recipient_profile", "sent_by", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("need__title", "recipient_profile__username", "sent_by__username")
    readonly_fields = ("created_at", "updated_at", "responded_at", "cancelled_at")
