from django.contrib import admin

from .inbound_models import InboundCapture
from .models import ActivityShareSubject, JourneyShareAcceptance, JourneyShareSubject, OpportunityShareSubject, ShareDelivery, ShareEnvelope, ShareLink

@admin.register(ShareEnvelope)
class ShareEnvelopeAdmin(admin.ModelAdmin):
    list_display = ("subject_type", "intent", "effective_status_display", "created_by", "created_at", "expires_at", "revoked_at")
    list_filter = ("subject_type", "intent", "status"); readonly_fields = ("created_at", "updated_at", "effective_status_display"); search_fields = ("created_by__email", "created_by__username")
    @admin.display(description="Statut effectif")
    def effective_status_display(self, obj): return obj.effective_status

@admin.register(ShareLink)
class ShareLinkAdmin(admin.ModelAdmin):
    list_display = ("envelope", "token_fingerprint", "created_at"); readonly_fields = ("envelope", "token_fingerprint", "created_at"); fields = ("envelope", "token_fingerprint", "created_at")

@admin.register(ShareDelivery)
class ShareDeliveryAdmin(admin.ModelAdmin):
    list_display = ("envelope", "recipient", "delivered_at", "opened_at", "accepted_at", "declined_at"); readonly_fields = list_display; search_fields = ("recipient__user__username", "recipient__user__first_name", "recipient__user__last_name")

@admin.register(ActivityShareSubject)
class ActivityShareSubjectAdmin(admin.ModelAdmin):
    list_display = ("envelope", "activity", "occurrence"); readonly_fields = list_display

@admin.register(OpportunityShareSubject)
class OpportunityShareSubjectAdmin(admin.ModelAdmin):
    list_display = ("envelope", "opportunity_revision"); readonly_fields = list_display

@admin.register(JourneyShareSubject)
class JourneyShareSubjectAdmin(admin.ModelAdmin):
    list_display = ("envelope", "source_journey", "schema_version", "created_at"); readonly_fields = ("envelope", "source_journey", "schema_version", "snapshot_summary", "created_at"); fields = readonly_fields
    @admin.display(description="Schema")
    def schema_version(self, obj): return obj.snapshot.get("schema_version") if isinstance(obj.snapshot, dict) else None
    @admin.display(description="Résumé sûr")
    def snapshot_summary(self, obj):
        counts = obj.snapshot.get("counts", {}) if isinstance(obj.snapshot, dict) else {}; return f"Réutilisable={counts.get('REUSABLE', 0)} · Personnaliser={counts.get('PERSONALIZE', 0)} · Revalider={counts.get('REVALIDATE', 0)}"

@admin.register(JourneyShareAcceptance)
class JourneyShareAcceptanceAdmin(admin.ModelAdmin):
    list_display = ("delivery", "resulting_journey", "accepted_at"); readonly_fields = list_display

@admin.register(InboundCapture)
class InboundCaptureAdmin(admin.ModelAdmin):
    list_display = ("id", "source_kind", "status", "created_by", "created_at", "expires_at", "absorbed_at")
    list_filter = ("source_kind", "status", "created_at"); readonly_fields = list_display + ("size", "mime_type", "absorbed_artifact", "absorbed_note")
    fields = readonly_fields
