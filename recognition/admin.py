from django.contrib import admin

from .models import (
    AchievementDefinition, AchievementGrant, RecognitionAccount, RecognitionAllocation,
    RecognitionCursor, RecognitionEvaluationWindow, RecognitionLedgerEntry,
    RecognitionObjectEvaluation, RecognitionPolicy, RecognitionRedemption,
    RecognitionRule, RecognitionSignal, RewardDefinition,
)


class RecognitionRuleInline(admin.StackedInline):
    model = RecognitionRule
    extra = 0


@admin.register(RecognitionPolicy)
class RecognitionPolicyAdmin(admin.ModelAdmin):
    list_display = ("code", "version", "name", "status", "effective_from", "effective_until")
    list_filter = ("status",)
    search_fields = ("code", "name")
    inlines = (RecognitionRuleInline,)


@admin.register(RecognitionSignal)
class RecognitionSignalAdmin(admin.ModelAdmin):
    list_display = ("signal_kind", "object_type", "object_id", "occurred_at", "available_at", "processed_at")
    list_filter = ("signal_kind", "processed_at")
    search_fields = ("signal_id", "outcome_identity", "object_id")
    readonly_fields = [field.name for field in RecognitionSignal._meta.fields]

    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False


@admin.register(RecognitionAccount)
class RecognitionAccountAdmin(admin.ModelAdmin):
    list_display = ("subject_type", "profile", "space", "points_balance", "pending_points", "lifetime_earned", "lifetime_spent")
    search_fields = ("profile__email", "space__name")
    readonly_fields = ("points_balance", "pending_points", "correction_deficit", "lifetime_earned", "lifetime_spent", "created_at", "updated_at")


for model in (RecognitionCursor, RecognitionEvaluationWindow, RecognitionObjectEvaluation, RecognitionAllocation, RecognitionLedgerEntry, AchievementGrant, RecognitionRedemption):
    admin.site.register(model)

admin.site.register(AchievementDefinition)
admin.site.register(RewardDefinition)
