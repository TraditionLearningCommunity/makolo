from django.contrib import admin

from .models import ActivityShareSubject, OpportunityShareSubject, ShareEnvelope, ShareLink


@admin.register(ShareEnvelope)
class ShareEnvelopeAdmin(admin.ModelAdmin):
    list_display = (
        "subject_type",
        "intent",
        "effective_status_display",
        "created_by",
        "created_at",
        "expires_at",
        "revoked_at",
    )
    list_filter = ("subject_type", "intent", "status")
    readonly_fields = ("created_at", "updated_at", "effective_status_display")
    search_fields = ("created_by__email", "created_by__username")

    @admin.display(description="Statut effectif")
    def effective_status_display(self, obj):
        return obj.effective_status


@admin.register(ShareLink)
class ShareLinkAdmin(admin.ModelAdmin):
    list_display = ("envelope", "token_fingerprint", "created_at")
    readonly_fields = ("envelope", "token_fingerprint", "created_at")
    fields = ("envelope", "token_fingerprint", "created_at")


@admin.register(ActivityShareSubject)
class ActivityShareSubjectAdmin(admin.ModelAdmin):
    list_display = ("envelope", "activity", "occurrence")
    readonly_fields = ("envelope", "activity", "occurrence")


@admin.register(OpportunityShareSubject)
class OpportunityShareSubjectAdmin(admin.ModelAdmin):
    list_display = ("envelope", "opportunity_revision")
    readonly_fields = ("envelope", "opportunity_revision")
