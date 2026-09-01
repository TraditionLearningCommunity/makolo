from django.contrib import admin

from .models import Dispute, Feedback, Proof, Report, TrustEvidence, VerificationClaim


class TrustAuditAdmin(admin.ModelAdmin):
    """Read-only audit view; workflow transitions must use Trust services."""

    def get_readonly_fields(self, request, obj=None):
        return tuple(field.name for field in self.model._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(VerificationClaim)
class VerificationClaimAdmin(TrustAuditAdmin):
    list_display = ("claim_type", "status", "subject_profile", "subject_space", "requested_at", "reviewed_at")
    list_filter = ("claim_type", "status", "disclosure")
    search_fields = ("subject_profile__email", "subject_space__name", "decision_reason_code")


@admin.register(Feedback)
class FeedbackAdmin(TrustAuditAdmin):
    list_display = ("journey", "author", "overall_sentiment", "moderation_status", "submitted_at", "withdrawn_at")
    list_filter = ("overall_sentiment", "moderation_status")
    search_fields = ("journey__id", "author__email")


@admin.register(Report)
class ReportAdmin(TrustAuditAdmin):
    list_display = ("category", "status", "reporter", "space", "created_at")
    list_filter = ("category", "status")
    search_fields = ("reporter__email", "space__name", "journey__id", "resolution_code")


@admin.register(Dispute)
class DisputeAdmin(TrustAuditAdmin):
    list_display = ("status", "claimant", "respondent_space", "respondent_profile", "decision_code", "created_at")
    list_filter = ("status", "remedy_code")
    search_fields = ("claimant__email", "respondent_space__name", "decision_code")


@admin.register(TrustEvidence)
class TrustEvidenceAdmin(TrustAuditAdmin):
    list_display = ("id", "verification_claim", "report", "uploaded_by", "created_at")
    search_fields = ("uploaded_by__email",)


@admin.register(Proof)
class ProofAdmin(TrustAuditAdmin):
    list_display = ("proof_type", "status", "subject_profile", "journey", "is_public", "issued_at")
    list_filter = ("proof_type", "status", "is_public")
    search_fields = ("subject_profile__email", "journey__id", "public_id")
