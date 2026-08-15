from django.contrib import admin

from .canonical_models import Audience, AudienceMember, CRMInteraction


@admin.register(CRMInteraction)
class CRMInteractionAdmin(admin.ModelAdmin):
    list_display = ("contact", "interaction_type", "activity", "occurred_at")
    list_filter = ("interaction_type", "occurred_at")
    search_fields = ("contact__email", "contact__name")
    raw_id_fields = ("contact", "domain_event", "activity")
    readonly_fields = ("domain_event", "occurred_at", "created_at")


@admin.register(Audience)
class AudienceAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "status", "created_at")
    list_filter = ("status", "organization")
    search_fields = ("name", "organization__name")
    raw_id_fields = ("created_by", "source_group", "source_snapshot")
    readonly_fields = ("created_at", "updated_at")


@admin.register(AudienceMember)
class AudienceMemberAdmin(admin.ModelAdmin):
    list_display = ("audience", "profile", "source", "added_at")
    list_filter = ("source", "added_at")
    search_fields = ("profile__email", "profile__first_name", "profile__last_name", "audience__name")
    raw_id_fields = ("audience", "profile", "source_group", "source_snapshot")
    readonly_fields = ("added_at",)
