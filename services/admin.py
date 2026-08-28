from django.contrib import admin

from .models import (
    ServiceDetails,
    ServiceIntakeAnswer,
    ServiceIntakeQuestion,
    ServiceJourneyContext,
    ServicePlanMaterialization,
    ServicePlanTemplate,
    ServicePlanTemplateStep,
    ServicePlanTemplateStepDependency,
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
    list_display = ("journey", "service_plan_template", "plan_materialized_at", "created_at")
    readonly_fields = ("plan_materialized_at", "created_at", "updated_at")


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
