from django.contrib import admin

from .models import (
    ServiceDetails,
    ServiceIntakeAnswer,
    ServiceIntakeQuestion,
    ServiceJourneyContext,
    ServiceOpportunityRevisionAdoption,
    ServiceOutcomeEvent,
    ServicePlanMaterialization,
    ServicePlanTemplate,
    ServicePlanTemplateStep,
    ServicePlanTemplateStepDependency,
    ServiceRequirementAssessment,
    ServiceRequirementEvidence,
    ServiceRequirementPaymentObligation,
    ServiceRequirementStepLink,
    ServiceSubmission,
)


@admin.register(ServiceDetails)
class ServiceDetailsAdmin(admin.ModelAdmin):
    list_display = ("activity", "service_kind", "opportunity_policy", "intake_policy", "completion_policy")
    list_filter = ("service_kind", "opportunity_policy", "intake_policy", "completion_policy")
    search_fields = ("activity__title",)


@admin.register(ServicePlanTemplate)
class ServicePlanTemplateAdmin(admin.ModelAdmin):
    list_display = ("service", "key", "version", "name", "status", "created_at")
    list_filter = ("status", "service")
    readonly_fields = ("created_at", "updated_at")


@admin.register(ServicePlanTemplateStep)
class ServicePlanTemplateStepAdmin(admin.ModelAdmin):
    list_display = ("template", "position", "kind", "title", "is_required")
    list_filter = ("kind", "is_required")


@admin.register(ServicePlanTemplateStepDependency)
class ServicePlanTemplateStepDependencyAdmin(admin.ModelAdmin):
    list_display = ("step", "depends_on", "created_at")
    readonly_fields = ("created_at",)


@admin.register(ServiceJourneyContext)
class ServiceJourneyContextAdmin(admin.ModelAdmin):
    list_display = ("journey", "service_plan_template", "opportunity", "opportunity_revision", "current_outcome", "plan_materialized_at", "created_at")
    readonly_fields = ("opportunity", "opportunity_revision", "current_outcome", "plan_materialized_at", "created_at", "updated_at")


@admin.register(ServiceRequirementAssessment)
class ServiceRequirementAssessmentAdmin(admin.ModelAdmin):
    list_display = ("context", "requirement", "status", "assessed_by", "assessed_at")
    list_filter = ("status",)
    readonly_fields = ("context", "requirement", "status", "note", "assessed_by", "assessed_at", "created_at", "updated_at")


@admin.register(ServiceRequirementEvidence)
class ServiceRequirementEvidenceAdmin(admin.ModelAdmin):
    list_display = ("assessment", "artifact", "status", "submitted_by", "reviewed_by", "reviewed_at")
    list_filter = ("status",)
    readonly_fields = ("assessment", "artifact", "status", "submitted_by", "reviewed_by", "reviewed_at", "review_note", "created_at", "updated_at")


@admin.register(ServiceOpportunityRevisionAdoption)
class ServiceOpportunityRevisionAdoptionAdmin(admin.ModelAdmin):
    list_display = ("context", "previous_revision", "revision", "adopted_by", "adopted_at")
    readonly_fields = ("context", "previous_revision", "revision", "adopted_by", "adopted_at")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ServiceRequirementStepLink)
class ServiceRequirementStepLinkAdmin(admin.ModelAdmin):
    list_display = ("assessment", "journey_step", "created_by", "created_at")
    readonly_fields = ("assessment", "journey_step", "created_by", "created_at")


@admin.register(ServiceRequirementPaymentObligation)
class ServiceRequirementPaymentObligationAdmin(admin.ModelAdmin):
    list_display = ("assessment", "obligation", "created_by", "created_at")
    readonly_fields = [field.name for field in ServiceRequirementPaymentObligation._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ServiceSubmission)
class ServiceSubmissionAdmin(admin.ModelAdmin):
    list_display = ("context", "attempt", "mode", "status", "submitted_at", "external_reference")
    list_filter = ("mode", "status")
    search_fields = ("context__journey__id", "external_reference", "receipt_artifact__title")
    readonly_fields = [field.name for field in ServiceSubmission._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ServiceOutcomeEvent)
class ServiceOutcomeEventAdmin(admin.ModelAdmin):
    list_display = ("context", "event_type", "occurred_at", "recorded_by", "created_at")
    list_filter = ("event_type", "occurred_at")
    search_fields = ("context__journey__id", "external_reference", "note")
    readonly_fields = [field.name for field in ServiceOutcomeEvent._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ServicePlanMaterialization)
class ServicePlanMaterializationAdmin(admin.ModelAdmin):
    list_display = ("context", "template_step", "journey_step", "created_at")
    readonly_fields = ("context", "template_step", "journey_step", "created_at")


@admin.register(ServiceIntakeQuestion)
class ServiceIntakeQuestionAdmin(admin.ModelAdmin):
    list_display = ("key", "question_type", "service", "template", "is_required", "position")
    list_filter = ("question_type", "is_required")


@admin.register(ServiceIntakeAnswer)
class ServiceIntakeAnswerAdmin(admin.ModelAdmin):
    list_display = ("journey", "question", "answered_by", "created_at")
    readonly_fields = ("journey", "question", "value", "answered_by", "created_at", "updated_at")
