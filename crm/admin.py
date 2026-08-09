from django.contrib import admin

from .models import (
    AudienceSegment,
    CampaignAttribution,
    CampaignRecipient,
    CampaignTemplate,
    CommunicationCampaign,
    CRMContact,
    CRMContactFieldValue,
    CRMContactNote,
    CRMContactTag,
    CRMCustomField,
    CRMTag,
)


@admin.register(CRMContact)
class CRMContactAdmin(admin.ModelAdmin):
    list_display = ("email", "name", "organization", "marketing_consent", "source", "last_seen_at")
    list_filter = ("organization", "marketing_consent", "source")
    search_fields = ("email", "name", "phone")
    readonly_fields = ("first_seen_at", "last_seen_at", "created_at", "updated_at")


@admin.register(CRMTag)
class CRMTagAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "color", "created_at")
    list_filter = ("organization",)
    search_fields = ("name", "organization__name")


@admin.register(CRMContactTag)
class CRMContactTagAdmin(admin.ModelAdmin):
    list_display = ("contact", "tag", "assigned_by", "created_at")
    list_filter = ("tag__organization", "tag")
    search_fields = ("contact__email", "tag__name")


@admin.register(CRMCustomField)
class CRMCustomFieldAdmin(admin.ModelAdmin):
    list_display = ("label", "key", "organization", "field_type", "is_active")
    list_filter = ("organization", "field_type", "is_active")
    search_fields = ("label", "key")


@admin.register(CRMContactFieldValue)
class CRMContactFieldValueAdmin(admin.ModelAdmin):
    list_display = ("contact", "field", "value", "updated_by", "updated_at")
    list_filter = ("field__organization", "field")
    search_fields = ("contact__email", "field__label")
    readonly_fields = ("created_at", "updated_at")


@admin.register(AudienceSegment)
class AudienceSegmentAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "event", "audience_kind", "marketing_consent_only", "is_active")
    list_filter = ("organization", "audience_kind", "marketing_consent_only", "is_active")
    search_fields = ("name", "description")
    filter_horizontal = ("required_tags",)


@admin.register(CampaignTemplate)
class CampaignTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "kind", "is_active", "use_count", "updated_at")
    list_filter = ("organization", "kind", "is_active")
    search_fields = ("name", "subject")
    readonly_fields = ("use_count", "created_at", "updated_at")


class CampaignRecipientInline(admin.TabularInline):
    model = CampaignRecipient
    extra = 0
    can_delete = False
    readonly_fields = ("contact", "email", "status", "attempts", "sent_at", "click_count", "first_clicked_at", "last_clicked_at", "last_error", "skipped_reason")


@admin.register(CommunicationCampaign)
class CommunicationCampaignAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "kind", "status", "track_conversions", "scheduled_at", "completed_at")
    list_filter = ("organization", "kind", "status", "track_conversions")
    search_fields = ("name", "subject")
    readonly_fields = ("started_at", "completed_at", "cancelled_at", "created_at", "updated_at")
    inlines = [CampaignRecipientInline]


@admin.register(CampaignRecipient)
class CampaignRecipientAdmin(admin.ModelAdmin):
    list_display = ("email", "campaign", "status", "attempts", "click_count", "scheduled_for", "sent_at")
    list_filter = ("status", "campaign__organization")
    search_fields = ("email", "name", "campaign__name")
    readonly_fields = ("created_at", "updated_at", "sent_at", "first_clicked_at", "last_clicked_at")


@admin.register(CampaignAttribution)
class CampaignAttributionAdmin(admin.ModelAdmin):
    list_display = ("campaign", "order", "status", "revenue_amount", "currency", "captured_at", "confirmed_at")
    list_filter = ("status", "currency", "campaign__organization")
    search_fields = ("campaign__name", "order__reference", "contact__email")
    readonly_fields = ("captured_at", "confirmed_at", "reversed_at")


@admin.register(CRMContactNote)
class CRMContactNoteAdmin(admin.ModelAdmin):
    list_display = ("contact", "author", "created_at")
    search_fields = ("contact__email", "body")
    readonly_fields = ("created_at",)
