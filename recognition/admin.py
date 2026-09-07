from datetime import timedelta

from django.contrib import admin, messages
from django.db import transaction
from django.utils import timezone

from authorization.constants import PermissionCode
from authorization.services import can

from .models import (
    AchievementDefinition, AchievementGrant, PolicyStatus, RecognitionAccount,
    RecognitionAllocation, RecognitionCursor, RecognitionEvaluationWindow,
    RecognitionLedgerEntry, RecognitionObjectEvaluation, RecognitionPolicy,
    RecognitionRedemption, RecognitionRule, RecognitionSignal, RewardDefinition,
)
from .simulation import simulate_policy


def _allowed(request, permission):
    return bool(request.user.is_superuser or can(request.user, permission))


class RecognitionRuleInline(admin.StackedInline):
    model = RecognitionRule
    extra = 0

    def has_add_permission(self, request, obj=None):
        return bool(obj and obj.status in {PolicyStatus.DRAFT, PolicyStatus.SIMULATED} and _allowed(request, PermissionCode.PLATFORM_RECOGNITION_POLICY_MANAGE))

    def has_change_permission(self, request, obj=None):
        return bool(obj and obj.status in {PolicyStatus.DRAFT, PolicyStatus.SIMULATED} and _allowed(request, PermissionCode.PLATFORM_RECOGNITION_POLICY_MANAGE))

    def has_delete_permission(self, request, obj=None):
        return self.has_change_permission(request, obj)


@admin.register(RecognitionPolicy)
class RecognitionPolicyAdmin(admin.ModelAdmin):
    list_display = ("code", "version", "name", "status", "effective_from", "effective_until")
    list_filter = ("status",)
    search_fields = ("code", "name")
    inlines = (RecognitionRuleInline,)
    actions = ("simulate_last_30_days", "publish_or_schedule")

    def has_module_permission(self, request):
        return _allowed(request, PermissionCode.PLATFORM_RECOGNITION_VIEW)

    def has_view_permission(self, request, obj=None):
        return _allowed(request, PermissionCode.PLATFORM_RECOGNITION_VIEW)

    def has_add_permission(self, request):
        return _allowed(request, PermissionCode.PLATFORM_RECOGNITION_POLICY_MANAGE)

    def has_change_permission(self, request, obj=None):
        if obj and obj.status not in {PolicyStatus.DRAFT, PolicyStatus.SIMULATED}:
            return False
        return _allowed(request, PermissionCode.PLATFORM_RECOGNITION_POLICY_MANAGE)

    def has_delete_permission(self, request, obj=None):
        return bool(obj and obj.status in {PolicyStatus.DRAFT, PolicyStatus.SIMULATED} and _allowed(request, PermissionCode.PLATFORM_RECOGNITION_POLICY_MANAGE))

    @admin.action(description="Simuler les Policies sur les 30 derniers jours")
    def simulate_last_30_days(self, request, queryset):
        if not _allowed(request, PermissionCode.PLATFORM_RECOGNITION_POLICY_MANAGE):
            self.message_user(request, "Permission Recognition insuffisante.", level=messages.ERROR)
            return
        now = timezone.now()
        for policy in queryset.filter(status__in=[PolicyStatus.DRAFT, PolicyStatus.SIMULATED]):
            result = simulate_policy(policy=policy, starts_at=now - timedelta(days=30), ends_at=now)
            RecognitionPolicy.objects.filter(pk=policy.pk).update(status=PolicyStatus.SIMULATED)
            self.message_user(request, f"{policy}: {result['projected_credits']} crédits projetés sur {result['signals']} Signals ({result['matches']} matches).", level=messages.INFO)

    @admin.action(description="Publier ou planifier la Policy simulée")
    def publish_or_schedule(self, request, queryset):
        if not _allowed(request, PermissionCode.PLATFORM_RECOGNITION_POLICY_PUBLISH):
            self.message_user(request, "Permission de publication Recognition insuffisante.", level=messages.ERROR)
            return
        policies = list(queryset)
        if len(policies) != 1:
            self.message_user(request, "Publiez une seule Policy à la fois.", level=messages.ERROR)
            return
        policy = policies[0]
        if policy.status not in {PolicyStatus.SIMULATED, PolicyStatus.SCHEDULED}:
            self.message_user(request, "La Policy doit être simulée avant publication.", level=messages.ERROR)
            return
        now = timezone.now()
        if policy.effective_from and policy.effective_from > now:
            RecognitionPolicy.objects.filter(pk=policy.pk).update(status=PolicyStatus.SCHEDULED)
            self.message_user(request, "Policy planifiée. Automation l'activera à une frontière de fenêtre.", level=messages.SUCCESS)
            return
        with transaction.atomic():
            RecognitionPolicy.objects.filter(status=PolicyStatus.ACTIVE).exclude(pk=policy.pk).update(status=PolicyStatus.SUPERSEDED, effective_until=now)
            RecognitionPolicy.objects.filter(pk=policy.pk).update(status=PolicyStatus.ACTIVE, effective_from=policy.effective_from or now)
        self.message_user(request, "Policy Recognition publiée.", level=messages.SUCCESS)


class ReadOnlyRecognitionAdmin(admin.ModelAdmin):
    def has_module_permission(self, request): return _allowed(request, PermissionCode.PLATFORM_RECOGNITION_AUDIT_VIEW)
    def has_view_permission(self, request, obj=None): return _allowed(request, PermissionCode.PLATFORM_RECOGNITION_AUDIT_VIEW)
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False


@admin.register(RecognitionSignal)
class RecognitionSignalAdmin(ReadOnlyRecognitionAdmin):
    list_display = ("signal_kind", "object_type", "object_id", "occurred_at", "available_at", "processed_at")
    list_filter = ("signal_kind", "processed_at")
    search_fields = ("signal_id", "outcome_identity", "object_id")
    readonly_fields = [field.name for field in RecognitionSignal._meta.fields]


@admin.register(RecognitionAccount)
class RecognitionAccountAdmin(ReadOnlyRecognitionAdmin):
    list_display = ("subject_type", "profile", "space", "points_balance", "pending_points", "lifetime_earned", "lifetime_spent")
    search_fields = ("profile__email", "space__name")


for model in (RecognitionCursor, RecognitionEvaluationWindow, RecognitionObjectEvaluation, RecognitionAllocation, RecognitionLedgerEntry, AchievementGrant, RecognitionRedemption):
    admin.site.register(model, ReadOnlyRecognitionAdmin)


@admin.register(AchievementDefinition)
class AchievementDefinitionAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_active", "is_publicly_presentable")
    def has_module_permission(self, request): return _allowed(request, PermissionCode.PLATFORM_RECOGNITION_ACHIEVEMENTS_MANAGE)
    def has_view_permission(self, request, obj=None): return _allowed(request, PermissionCode.PLATFORM_RECOGNITION_ACHIEVEMENTS_MANAGE)
    def has_add_permission(self, request): return _allowed(request, PermissionCode.PLATFORM_RECOGNITION_ACHIEVEMENTS_MANAGE)
    def has_change_permission(self, request, obj=None): return _allowed(request, PermissionCode.PLATFORM_RECOGNITION_ACHIEVEMENTS_MANAGE)
    def has_delete_permission(self, request, obj=None): return _allowed(request, PermissionCode.PLATFORM_RECOGNITION_ACHIEVEMENTS_MANAGE)


@admin.register(RewardDefinition)
class RewardDefinitionAdmin(admin.ModelAdmin):
    list_display = ("code", "version", "name", "kind", "points_cost", "is_active")
    def has_module_permission(self, request): return _allowed(request, PermissionCode.PLATFORM_RECOGNITION_ECONOMY_MANAGE)
    def has_view_permission(self, request, obj=None): return _allowed(request, PermissionCode.PLATFORM_RECOGNITION_ECONOMY_MANAGE)
    def has_add_permission(self, request): return _allowed(request, PermissionCode.PLATFORM_RECOGNITION_ECONOMY_MANAGE)
    def has_change_permission(self, request, obj=None): return _allowed(request, PermissionCode.PLATFORM_RECOGNITION_ECONOMY_MANAGE)
    def has_delete_permission(self, request, obj=None): return _allowed(request, PermissionCode.PLATFORM_RECOGNITION_ECONOMY_MANAGE)
