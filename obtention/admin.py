from django.contrib import admin

from .models import (
    ObtentionConfiguration,
    ObtentionDetails,
    ObtentionJourneyContext,
    ObtentionMode,
    ObtentionTarget,
    ObtentionTargetReceipt,
)


@admin.register(ObtentionDetails)
class ObtentionDetailsAdmin(admin.ModelAdmin):
    list_display = ("activity", "created_at")
    search_fields = ("activity__title", "activity__space__name", "activity__owner_profile__email")
    list_select_related = ("activity",)


@admin.register(ObtentionConfiguration)
class ObtentionConfigurationAdmin(admin.ModelAdmin):
    list_display = ("obtention", "version", "status", "result_label", "published_at")
    list_filter = ("status", "target_rule", "beneficiary_confirmation_required", "operator_confirmation_required")
    list_select_related = ("obtention", "obtention__activity")


admin.site.register(ObtentionTarget)
admin.site.register(ObtentionMode)
admin.site.register(ObtentionJourneyContext)
admin.site.register(ObtentionTargetReceipt)
