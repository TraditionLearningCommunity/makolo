from django.contrib import admin

from .models import AudienceSegment, CampaignRecipient, CommunicationCampaign, CRMContact, CRMContactNote


@admin.register(CRMContact)
class CRMContactAdmin(admin.ModelAdmin):
    list_display = ("email", "name", "organization", "marketing_consent", "source", "last_seen_at")
    list_filter = ("organization", "marketing_consent", "source")
    search_fields = ("email", "name", "phone")
    readonly_fields = ("first_seen_at", "last_seen_at", "created_at", "updated_at")


@admin.register(AudienceSegment)
class AudienceSegmentAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "event", "audience_kind", "marketing_consent_only", "is_active")
    list_filter = ("organization", "audience_kind", "marketing_consent_only", "is_active")
    search_fields = ("name", "description")


class CampaignRecipientInline(admin.TabularInline):
    model = CampaignRecipient
    extra = 0
    can_delete = False
    readonly_fields = ("contact", "email", "status", "attempts", "sent_at", "last_error", "skipped_reason")


@admin.register(CommunicationCampaign)
class CommunicationCampaignAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "kind", "status", "scheduled_at", "completed_at")
    list_filter = ("organization", "kind", "status")
    search_fields = ("name", "subject")
    readonly_fields = ("started_at", "completed_at", "cancelled_at", "created_at", "updated_at")
    inlines = [CampaignRecipientInline]


@admin.register(CampaignRecipient)
class CampaignRecipientAdmin(admin.ModelAdmin):
    list_display = ("email", "campaign", "status", "attempts", "scheduled_for", "sent_at")
    list_filter = ("status", "campaign__organization")
    search_fields = ("email", "name", "campaign__name")
    readonly_fields = ("created_at", "updated_at", "sent_at")


@admin.register(CRMContactNote)
class CRMContactNoteAdmin(admin.ModelAdmin):
    list_display = ("contact", "author", "created_at")
    search_fields = ("contact__email", "body")
    readonly_fields = ("created_at",)
