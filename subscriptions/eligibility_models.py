from __future__ import annotations

import uuid

from django.core.exceptions import ValidationError
from django.db import models

from organizations.models import Organization
from requirements.contracts import RequirementMode
from requirements.registry import RequirementConfigurationError, RequirementRegistryError, registry

from .contracts import (
    PlanVersionStatus,
    RequirementDisclosure,
    RequirementFailurePolicy,
    RequirementPhase,
    SubscriptionSubjectType,
)
from .models import PlanEntitlement, PlanVersion, technical_code_validator


_PHASE_POLICIES = {
    RequirementPhase.ACQUISITION: {RequirementFailurePolicy.BLOCK, RequirementFailurePolicy.DENY},
    RequirementPhase.ONGOING: {
        RequirementFailurePolicy.WARN,
        RequirementFailurePolicy.GRACE,
        RequirementFailurePolicy.SUSPEND,
    },
    RequirementPhase.RENEWAL: {RequirementFailurePolicy.BLOCK, RequirementFailurePolicy.DENY},
}


def _definition_supports_subject(definition, subject_type):
    supported = definition.supported_subject_type
    supported_types = supported if isinstance(supported, tuple) else (supported,)
    if subject_type == SubscriptionSubjectType.SPACE:
        return any(issubclass(item, Organization) for item in supported_types)
    from django.contrib.auth import get_user_model

    User = get_user_model()
    return any(issubclass(item, User) for item in supported_types)


def validate_evaluator_configuration(*, mode, evaluator_key, config, subject_type):
    if mode == RequirementMode.AUTOMATIC:
        if not evaluator_key:
            raise ValidationError({"evaluator_key": "Un Requirement automatic exige un evaluator connu."})
    elif not evaluator_key:
        if config not in ({}, None):
            raise ValidationError({"config": "Une config evaluator exige evaluator_key."})
        return {}

    if not evaluator_key:
        return {}
    try:
        definition = registry.get(evaluator_key)
        normalized = registry.validate_config(evaluator_key, config or {})
    except (RequirementRegistryError, RequirementConfigurationError) as exc:
        raise ValidationError({"config": str(exc)}) from exc
    if not _definition_supports_subject(definition, subject_type):
        raise ValidationError({"evaluator_key": "Cet evaluator ne supporte pas le type de sujet du Plan."})
    return normalized


class PlanRequirementQuerySet(models.QuerySet):
    def update(self, **kwargs):
        if self.exclude(plan_version__status=PlanVersionStatus.DRAFT).exists():
            raise ValidationError("Les Requirements d'une PlanVersion publiée ou retirée sont immuables.")
        return super().update(**kwargs)

    def delete(self):
        if self.exclude(plan_version__status=PlanVersionStatus.DRAFT).exists():
            raise ValidationError("Les Requirements d'une PlanVersion publiée ou retirée sont immuables.")
        return super().delete()


class PlanRequirement(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    plan_version = models.ForeignKey(PlanVersion, on_delete=models.CASCADE, related_name="requirements")
    key = models.CharField(max_length=120, validators=[technical_code_validator])
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    phase = models.CharField(max_length=16, choices=RequirementPhase.choices)
    mode = models.CharField(max_length=20, choices=RequirementMode.choices)
    evaluator_key = models.CharField(max_length=160, blank=True)
    config = models.JSONField(default=dict, blank=True)
    is_mandatory = models.BooleanField(default=True)
    position = models.PositiveIntegerField(default=0)
    failure_policy = models.CharField(max_length=16, choices=RequirementFailurePolicy.choices)
    grace_period_days = models.PositiveIntegerField(null=True, blank=True)
    disclosure = models.CharField(max_length=12, choices=RequirementDisclosure.choices, default=RequirementDisclosure.VISIBLE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = PlanRequirementQuerySet.as_manager()

    class Meta:
        ordering = ["plan_version", "phase", "position", "key"]
        constraints = [
            models.UniqueConstraint(fields=["plan_version", "key"], name="subs_plan_requirement_key_unique"),
            models.UniqueConstraint(fields=["plan_version", "phase", "position"], name="subs_plan_requirement_position_unique"),
        ]
        indexes = [
            models.Index(fields=["plan_version", "phase", "is_mandatory"], name="subs_plan_req_phase_idx"),
            models.Index(fields=["evaluator_key"], name="subs_plan_req_eval_idx"),
        ]

    def clean(self):
        super().clean()
        errors = {}
        allowed = _PHASE_POLICIES.get(self.phase, set())
        if self.failure_policy not in allowed:
            errors["failure_policy"] = "Cette policy n'est pas compatible avec la phase du Requirement."
        if self.grace_period_days is not None and not (
            self.phase == RequirementPhase.ONGOING and self.failure_policy == RequirementFailurePolicy.GRACE
        ):
            errors["grace_period_days"] = "grace_period_days est réservé à ongoing + grace."
        if self.grace_period_days is not None and self.grace_period_days > 3650:
            errors["grace_period_days"] = "La période de grâce ne peut pas dépasser 3650 jours."
        if self.plan_version_id:
            try:
                self.config = validate_evaluator_configuration(
                    mode=self.mode,
                    evaluator_key=self.evaluator_key,
                    config=self.config,
                    subject_type=self.plan_version.plan.subject_type,
                )
            except ValidationError as exc:
                errors.update(exc.message_dict)
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        status = PlanVersion.objects.filter(pk=self.plan_version_id).values_list("status", flat=True).first()
        if status and status != PlanVersionStatus.DRAFT:
            raise ValidationError("Les Requirements d'une PlanVersion publiée ou retirée sont immuables.")
        if self.pk and not self._state.adding:
            previous = type(self).objects.filter(pk=self.pk).values_list("plan_version_id", flat=True).first()
            if previous and previous != self.plan_version_id:
                old_status = PlanVersion.objects.filter(pk=previous).values_list("status", flat=True).first()
                if old_status and old_status != PlanVersionStatus.DRAFT:
                    raise ValidationError("Les Requirements d'une PlanVersion publiée ou retirée sont immuables.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        status = PlanVersion.objects.filter(pk=self.plan_version_id).values_list("status", flat=True).first()
        if status and status != PlanVersionStatus.DRAFT:
            raise ValidationError("Les Requirements d'une PlanVersion publiée ou retirée sont immuables.")
        return super().delete(*args, **kwargs)


class EntitlementRequirementQuerySet(models.QuerySet):
    def update(self, **kwargs):
        if self.exclude(plan_entitlement__plan_version__status=PlanVersionStatus.DRAFT).exists():
            raise ValidationError("Les Requirements d'un Entitlement publié ou retiré sont immuables.")
        return super().update(**kwargs)

    def delete(self):
        if self.exclude(plan_entitlement__plan_version__status=PlanVersionStatus.DRAFT).exists():
            raise ValidationError("Les Requirements d'un Entitlement publié ou retiré sont immuables.")
        return super().delete()


class EntitlementRequirement(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    plan_entitlement = models.ForeignKey(PlanEntitlement, on_delete=models.CASCADE, related_name="requirements")
    key = models.CharField(max_length=120, validators=[technical_code_validator])
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    mode = models.CharField(max_length=20, choices=RequirementMode.choices)
    evaluator_key = models.CharField(max_length=160, blank=True)
    config = models.JSONField(default=dict, blank=True)
    is_mandatory = models.BooleanField(default=True)
    position = models.PositiveIntegerField(default=0)
    disclosure = models.CharField(max_length=12, choices=RequirementDisclosure.choices, default=RequirementDisclosure.VISIBLE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = EntitlementRequirementQuerySet.as_manager()

    class Meta:
        ordering = ["plan_entitlement", "position", "key"]
        constraints = [
            models.UniqueConstraint(fields=["plan_entitlement", "key"], name="subs_ent_requirement_key_unique"),
            models.UniqueConstraint(fields=["plan_entitlement", "position"], name="subs_ent_requirement_position_unique"),
        ]
        indexes = [models.Index(fields=["evaluator_key"], name="subs_ent_req_eval_idx")]

    def clean(self):
        super().clean()
        if not self.plan_entitlement_id:
            return
        self.config = validate_evaluator_configuration(
            mode=self.mode,
            evaluator_key=self.evaluator_key,
            config=self.config,
            subject_type=self.plan_entitlement.plan_version.plan.subject_type,
        )

    def save(self, *args, **kwargs):
        status = PlanEntitlement.objects.filter(pk=self.plan_entitlement_id).values_list(
            "plan_version__status", flat=True
        ).first()
        if status and status != PlanVersionStatus.DRAFT:
            raise ValidationError("Les Requirements d'un Entitlement publié ou retiré sont immuables.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        status = PlanEntitlement.objects.filter(pk=self.plan_entitlement_id).values_list(
            "plan_version__status", flat=True
        ).first()
        if status and status != PlanVersionStatus.DRAFT:
            raise ValidationError("Les Requirements d'un Entitlement publié ou retiré sont immuables.")
        return super().delete(*args, **kwargs)
