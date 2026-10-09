from datetime import timedelta
from math import ceil

from django import forms
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.template.response import TemplateResponse
from django.utils import timezone

from authorization.constants import PermissionCode
from authorization.services import can

from .models import (
    AchievementDefinition, AchievementGrant, PolicyStatus, RecognitionAccount,
    RecognitionAllocation, RecognitionCursor, RecognitionEvaluationWindow,
    RecognitionLedgerEntry, RecognitionObjectEvaluation, RecognitionPolicy,
    RecognitionRedemption, RecognitionRule, RecognitionSignal, RewardDefinition,
)
from .governance_services import record_policy_simulation, publish_policy_for_actor


def _allowed(request, permission):
    return bool(request.user.is_superuser or can(request.user, permission))


def _next_policy_boundary(*, cursor, target):
    """First Recognition window boundary at or after target."""
    if cursor is None:
        return target
    window = timedelta(hours=cursor.window_size_hours)
    if target <= cursor.last_completed_end:
        return cursor.last_completed_end + window
    distance = target - cursor.last_completed_end
    steps = max(1, ceil(distance.total_seconds() / window.total_seconds()))
    return cursor.last_completed_end + (window * steps)


class RecognitionRuleInline(admin.StackedInline):
    model = RecognitionRule
    extra = 0

    def has_add_permission(self, request, obj=None):
        return bool(obj and obj.status in {PolicyStatus.DRAFT, PolicyStatus.SIMULATED} and _allowed(request, PermissionCode.PLATFORM_RECOGNITION_POLICY_MANAGE))

    def has_change_permission(self, request, obj=None):
        return bool(obj and obj.status in {PolicyStatus.DRAFT, PolicyStatus.SIMULATED} and _allowed(request, PermissionCode.PLATFORM_RECOGNITION_POLICY_MANAGE))

    def has_delete_permission(self, request, obj=None):
        return self.has_change_permission(request, obj)


class RecognitionPolicyDecisionForm(forms.Form):
    reason = forms.CharField(
        min_length=5, max_length=2000,
        widget=forms.Textarea(attrs={"rows": 3}),
        label="Justification obligatoire",
    )
    expected_status = forms.CharField(widget=forms.HiddenInput)


@admin.register(RecognitionPolicy)
class RecognitionPolicyAdmin(admin.ModelAdmin):
    list_display = ("code", "version", "name", "status", "effective_from", "effective_until")
    list_filter = ("status",)
    search_fields = ("code", "name")
    inlines = (RecognitionRuleInline,)
    # Status transitions must only happen through explicit policy actions.
    readonly_fields = ("status", "effective_until")
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

    def _confirm_policy_action(self, request, queryset, *, action, title, service, permission):
        if not _allowed(request, permission):
            raise PermissionDenied("Autorité Recognition insuffisante.")
        policy_ids = list(queryset.values_list("pk", flat=True)[:2])
        if len(policy_ids) != 1:
            self.message_user(request, "Sélectionnez une seule Policy.", level=messages.ERROR)
            return
        policy = queryset.get(pk=policy_ids[0])
        if request.POST.get("confirm_governance") == "1":
            form = RecognitionPolicyDecisionForm(request.POST)
            if form.is_valid():
                try:
                    service(
                        actor=request.user, policy_id=policy.pk,
                        expected_status=form.cleaned_data["expected_status"],
                        reason=form.cleaned_data["reason"],
                    )
                except ValidationError as error:
                    form.add_error(None, error)
                else:
                    self.message_user(request, "Décision Recognition enregistrée et auditée.", level=messages.SUCCESS)
                    return
        else:
            form = RecognitionPolicyDecisionForm(initial={"expected_status": policy.status})
        return TemplateResponse(
            request,
            "admin/recognition/recognitionpolicy/confirm_action.html",
            {
                **self.admin_site.each_context(request),
                "title": title,
                "opts": self.model._meta,
                "policy": policy,
                "form": form,
                "action": action,
                "action_checkbox_name": admin.helpers.ACTION_CHECKBOX_NAME,
            },
        )

    @admin.action(description="Simuler la Policy (confirmation et justification)")
    def simulate_last_30_days(self, request, queryset):
        return self._confirm_policy_action(
            request, queryset,
            action="simulate_last_30_days",
            title="Simulation Recognition — action auditée",
            service=record_policy_simulation,
            permission=PermissionCode.PLATFORM_RECOGNITION_POLICY_MANAGE,
        )

    @admin.action(description="Publier ou planifier la Policy (confirmation et justification)")
    def publish_or_schedule(self, request, queryset):
        return self._confirm_policy_action(
            request, queryset,
            action="publish_or_schedule",
            title="Publication Recognition — action auditée",
            service=publish_policy_for_actor,
            permission=PermissionCode.PLATFORM_RECOGNITION_POLICY_PUBLISH,
        )


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
    def has_change_permission(self, request, obj=None):
        return _allowed(request, PermissionCode.PLATFORM_RECOGNITION_ACHIEVEMENTS_MANAGE) and not (obj and obj.grants.exists())
    def has_delete_permission(self, request, obj=None):
        # No generic/bulk deletion of published economy definitions.
        return False


@admin.register(RewardDefinition)
class RewardDefinitionAdmin(admin.ModelAdmin):
    list_display = ("code", "version", "name", "kind", "points_cost", "is_active")
    def has_module_permission(self, request): return _allowed(request, PermissionCode.PLATFORM_RECOGNITION_ECONOMY_MANAGE)
    def has_view_permission(self, request, obj=None): return _allowed(request, PermissionCode.PLATFORM_RECOGNITION_ECONOMY_MANAGE)
    def has_add_permission(self, request): return _allowed(request, PermissionCode.PLATFORM_RECOGNITION_ECONOMY_MANAGE)
    def has_change_permission(self, request, obj=None):
        return _allowed(request, PermissionCode.PLATFORM_RECOGNITION_ECONOMY_MANAGE) and not (obj and obj.redemptions.exists())
    def has_delete_permission(self, request, obj=None):
        # Definitions are versioned and may be referenced by historic redemptions.
        return False
