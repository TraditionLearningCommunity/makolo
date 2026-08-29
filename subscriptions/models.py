from __future__ import annotations

import math
import uuid
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Q

from .contracts import (
    AcquisitionMode,
    CatalogVisibility,
    EntitlementAggregationStrategy,
    FeatureEnforcementPolicy,
    FeatureValueType,
    PlanVersionStatus,
    SubscriptionPlanType,
    SubscriptionSubjectType,
)


technical_code_validator = RegexValidator(
    regex=r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$",
    message="Utilisez un code technique stable en minuscules (segments séparés par ., _ ou -).",
)


def _changed(previous, instance, fields):
    return [field for field in fields if previous[field] != getattr(instance, field)]


class FeatureDefinitionQuerySet(models.QuerySet):
    def update(self, **kwargs):
        protected = set(FeatureDefinition.TECHNICAL_FIELDS)
        if protected.intersection(kwargs):
            raise ValidationError("Le contrat technique d'une Feature existante est immuable.")
        return super().update(**kwargs)


class FeatureDefinition(models.Model):
    TECHNICAL_FIELDS = (
        "code", "domain", "value_type", "unit", "supports_profile", "supports_space",
        "aggregation_strategy", "usage_provider", "enforcement_policy", "minimum_value",
        "maximum_value", "enum_values",
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=120, unique=True, validators=[technical_code_validator])
    name = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    domain = models.CharField(max_length=80, validators=[technical_code_validator])
    value_type = models.CharField(max_length=16, choices=FeatureValueType.choices)
    unit = models.CharField(max_length=40, blank=True)
    supports_profile = models.BooleanField(default=False)
    supports_space = models.BooleanField(default=False)
    aggregation_strategy = models.CharField(max_length=16, choices=EntitlementAggregationStrategy.choices)
    usage_provider = models.CharField(max_length=120, blank=True, validators=[technical_code_validator])
    enforcement_policy = models.CharField(max_length=40, choices=FeatureEnforcementPolicy.choices)
    minimum_value = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    maximum_value = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    enum_values = models.JSONField(default=list, blank=True, encoder=DjangoJSONEncoder)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = FeatureDefinitionQuerySet.as_manager()

    class Meta:
        ordering = ["domain", "code"]
        constraints = [
            models.CheckConstraint(
                condition=Q(supports_profile=True) | Q(supports_space=True),
                name="subs_feature_has_subject",
            ),
            models.CheckConstraint(
                condition=Q(minimum_value__isnull=True)
                | Q(maximum_value__isnull=True)
                | Q(minimum_value__lte=models.F("maximum_value")),
                name="subs_feature_value_range",
            ),
        ]
        indexes = [
            models.Index(fields=["domain", "is_active"], name="subs_feature_domain_active_idx"),
            models.Index(fields=["value_type", "is_active"], name="subs_feature_type_active_idx"),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if not self.supports_profile and not self.supports_space:
            errors["supports_profile"] = "Une Feature doit supporter au moins un type de sujet."

        enum_values = self.enum_values or []
        if self.value_type == FeatureValueType.ENUM:
            if not isinstance(enum_values, list) or not enum_values:
                errors["enum_values"] = "Une Feature enum doit définir au moins une valeur autorisée."
            elif any(not isinstance(item, str) or not item.strip() for item in enum_values):
                errors["enum_values"] = "Les valeurs enum doivent être des chaînes non vides."
            elif len(set(enum_values)) != len(enum_values):
                errors["enum_values"] = "Les valeurs enum doivent être uniques."
            if self.minimum_value is not None or self.maximum_value is not None:
                errors["minimum_value"] = "Une Feature enum ne porte pas de borne numérique."
            if self.aggregation_strategy != EntitlementAggregationStrategy.REPLACE:
                errors["aggregation_strategy"] = "Une Feature enum utilise REPLACE."
        elif enum_values:
            errors["enum_values"] = "enum_values est réservé aux Features enum."

        if self.value_type == FeatureValueType.BOOLEAN:
            if self.minimum_value is not None or self.maximum_value is not None:
                errors["minimum_value"] = "Une Feature booléenne ne porte pas de borne numérique."
            if self.aggregation_strategy not in {
                EntitlementAggregationStrategy.BOOLEAN_OR,
                EntitlementAggregationStrategy.REPLACE,
            }:
                errors["aggregation_strategy"] = "Une Feature booléenne utilise BOOLEAN_OR ou REPLACE."
            if self.enforcement_policy != FeatureEnforcementPolicy.FEATURE_GATE:
                errors["enforcement_policy"] = "Une Feature booléenne utilise feature_gate."
            if self.usage_provider:
                errors["usage_provider"] = "Une Feature booléenne n'a pas de compteur d'usage."

        if self.value_type in {FeatureValueType.INTEGER, FeatureValueType.DECIMAL}:
            if self.aggregation_strategy == EntitlementAggregationStrategy.BOOLEAN_OR:
                errors["aggregation_strategy"] = "Une Feature numérique ne peut pas utiliser BOOLEAN_OR."
            if (
                self.enforcement_policy == FeatureEnforcementPolicy.PRESERVE_EXISTING_BLOCK_NEW
                and not self.usage_provider
            ):
                errors["usage_provider"] = "Une limite mesurée doit déclarer son provider d'usage."
            if self.value_type == FeatureValueType.INTEGER:
                for field in ("minimum_value", "maximum_value"):
                    bound = getattr(self, field)
                    if bound is not None and bound != bound.to_integral_value():
                        errors[field] = "Les bornes d'une Feature entière doivent être entières."

        if self.minimum_value is not None and self.maximum_value is not None:
            if self.minimum_value > self.maximum_value:
                errors["maximum_value"] = "La borne maximale doit être >= à la borne minimale."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding:
            previous = type(self).objects.filter(pk=self.pk).values(*self.TECHNICAL_FIELDS).first()
            changed = _changed(previous, self, self.TECHNICAL_FIELDS) if previous else []
            if changed:
                raise ValidationError({field: "Le contrat technique d'une Feature est immuable." for field in changed})
        self.full_clean()
        return super().save(*args, **kwargs)

    def supports_subject_type(self, subject_type):
        return (
            subject_type == SubscriptionSubjectType.PROFILE and self.supports_profile
        ) or (
            subject_type == SubscriptionSubjectType.SPACE and self.supports_space
        )

    def normalize_entitlement_value(self, value):
        if self.value_type == FeatureValueType.BOOLEAN:
            if type(value) is not bool:
                raise ValidationError({"value": "Cette Feature exige un booléen strict."})
            return value
        if self.value_type == FeatureValueType.INTEGER:
            if type(value) is not int:
                raise ValidationError({"value": "Cette Feature exige un entier strict."})
            self._validate_numeric_range(Decimal(value))
            return value
        if self.value_type == FeatureValueType.DECIMAL:
            if isinstance(value, bool) or isinstance(value, (dict, list)) or value is None:
                raise ValidationError({"value": "Cette Feature exige un décimal fini."})
            if isinstance(value, float) and not math.isfinite(value):
                raise ValidationError({"value": "Cette Feature exige un décimal fini."})
            try:
                numeric = Decimal(str(value))
            except (InvalidOperation, ValueError):
                raise ValidationError({"value": "Cette Feature exige un décimal fini."})
            if not numeric.is_finite():
                raise ValidationError({"value": "Cette Feature exige un décimal fini."})
            self._validate_numeric_range(numeric)
            return format(numeric.normalize(), "f")
        if self.value_type == FeatureValueType.ENUM:
            if not isinstance(value, str) or value not in self.enum_values:
                raise ValidationError({"value": "Valeur non autorisée par la Feature enum."})
            return value
        raise ValidationError({"value": "Type de Feature non supporté."})

    def _validate_numeric_range(self, value):
        if self.minimum_value is not None and value < self.minimum_value:
            raise ValidationError({"value": f"La valeur doit être >= {self.minimum_value}."})
        if self.maximum_value is not None and value > self.maximum_value:
            raise ValidationError({"value": f"La valeur doit être <= {self.maximum_value}."})

    def __str__(self):
        return f"{self.code} — {self.name}"


class SubscriptionPlanQuerySet(models.QuerySet):
    def update(self, **kwargs):
        if {"code", "plan_type", "subject_type", "current_version", "current_version_id"}.intersection(kwargs):
            raise ValidationError("L'identité du Plan et current_version ne se modifient pas en masse.")
        return super().update(**kwargs)


class SubscriptionPlan(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=120, unique=True, validators=[technical_code_validator])
    plan_type = models.CharField(max_length=12, choices=SubscriptionPlanType.choices)
    subject_type = models.CharField(max_length=12, choices=SubscriptionSubjectType.choices)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    current_version = models.ForeignKey(
        "PlanVersion", on_delete=models.SET_NULL, related_name="current_for_plans", null=True, blank=True
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_subscription_plans",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = SubscriptionPlanQuerySet.as_manager()

    class Meta:
        ordering = ["subject_type", "plan_type", "code"]
        constraints = [
            models.CheckConstraint(
                condition=Q(plan_type=SubscriptionPlanType.BASE) | Q(is_default=False),
                name="subs_default_only_base",
            ),
            models.UniqueConstraint(
                fields=["subject_type"],
                condition=Q(plan_type=SubscriptionPlanType.BASE, is_default=True, is_active=True),
                name="subs_one_active_default_base",
            ),
        ]
        indexes = [
            models.Index(fields=["subject_type", "plan_type", "is_active"], name="subs_plan_subject_type_idx")
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.is_default and self.plan_type != SubscriptionPlanType.BASE:
            errors["is_default"] = "Seul un plan BASE peut être le plan par défaut."
        if self.current_version_id:
            if self.current_version.plan_id != self.pk:
                errors["current_version"] = "La version courante doit appartenir à ce Plan."
            elif self.current_version.status != PlanVersionStatus.PUBLISHED:
                errors["current_version"] = "La version courante doit être publiée."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding:
            previous = type(self).objects.filter(pk=self.pk).values(
                "code", "plan_type", "subject_type", "current_version_id"
            ).first()
            if previous:
                changed = _changed(previous, self, ("code", "plan_type", "subject_type"))
                if changed:
                    raise ValidationError({field: "L'identité technique d'un Plan est immuable." for field in changed})
                if previous["current_version_id"] != self.current_version_id and not getattr(
                    self, "_allow_current_version_change", False
                ):
                    raise ValidationError({"current_version": "current_version est contrôlée par la publication."})
        self.full_clean()
        result = super().save(*args, **kwargs)
        self._allow_current_version_change = False
        return result

    def __str__(self):
        return self.code


class PlanVersionQuerySet(models.QuerySet):
    def update(self, **kwargs):
        if "status" in kwargs:
            raise ValidationError("Le statut d'une PlanVersion passe par les services métier.")
        if self.exclude(status=PlanVersionStatus.DRAFT).exists():
            raise ValidationError("Une PlanVersion publiée ou retirée est immuable.")
        return super().update(**kwargs)

    def delete(self):
        if self.exclude(status=PlanVersionStatus.DRAFT).exists():
            raise ValidationError("Une PlanVersion publiée ou retirée ne peut pas être supprimée.")
        return super().delete()


class PlanVersion(models.Model):
    STRUCTURAL_FIELDS = (
        "plan_id", "version", "name", "short_description", "description",
        "catalog_visibility", "acquisition_mode", "display_order", "change_summary", "created_by_id",
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT, related_name="versions")
    version = models.PositiveIntegerField()
    status = models.CharField(max_length=12, choices=PlanVersionStatus.choices, default=PlanVersionStatus.DRAFT)
    name = models.CharField(max_length=180)
    short_description = models.CharField(max_length=320, blank=True)
    description = models.TextField(blank=True)
    catalog_visibility = models.CharField(max_length=12, choices=CatalogVisibility.choices, default=CatalogVisibility.PUBLIC)
    acquisition_mode = models.CharField(max_length=16, choices=AcquisitionMode.choices, default=AcquisitionMode.SELF_SERVICE)
    display_order = models.IntegerField(default=0)
    change_summary = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_subscription_plan_versions",
        null=True,
        blank=True,
    )
    published_at = models.DateTimeField(null=True, blank=True)
    retired_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = PlanVersionQuerySet.as_manager()

    class Meta:
        ordering = ["plan", "version"]
        constraints = [
            models.UniqueConstraint(fields=["plan", "version"], name="subs_plan_version_unique"),
            models.CheckConstraint(condition=Q(version__gte=1), name="subs_plan_version_positive"),
        ]
        indexes = [
            models.Index(fields=["status", "catalog_visibility"], name="subs_version_catalog_idx"),
            models.Index(fields=["plan", "status"], name="subs_version_plan_status_idx"),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.status == PlanVersionStatus.DRAFT:
            if self.published_at is not None:
                errors["published_at"] = "Une version draft n'a pas de date de publication."
            if self.retired_at is not None:
                errors["retired_at"] = "Une version draft ne peut pas être retirée."
        elif self.status == PlanVersionStatus.PUBLISHED:
            if self.published_at is None:
                errors["published_at"] = "Une version publiée conserve sa date de publication."
            if self.retired_at is not None:
                errors["retired_at"] = "Une version publiée n'a pas encore de date de retrait."
        elif self.status == PlanVersionStatus.RETIRED:
            if self.published_at is None or self.retired_at is None:
                errors["retired_at"] = "Une version retirée conserve publication et retrait."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self._state.adding and self.status != PlanVersionStatus.DRAFT and not getattr(
            self, "_allow_status_transition", False
        ):
            raise ValidationError({"status": "Créez la version en draft puis publiez-la via le service métier."})

        if self.pk and not self._state.adding:
            previous = type(self).objects.filter(pk=self.pk).values(
                "status", "published_at", "retired_at", *self.STRUCTURAL_FIELDS
            ).first()
            if previous:
                if previous["status"] != PlanVersionStatus.DRAFT:
                    changed = _changed(previous, self, self.STRUCTURAL_FIELDS)
                    if changed:
                        raise ValidationError({field: "Une PlanVersion publiée ou retirée est immuable." for field in changed})
                    if previous["published_at"] != self.published_at:
                        raise ValidationError({"published_at": "La date de publication est immuable."})
                    if previous["status"] == self.status and previous["retired_at"] != self.retired_at:
                        raise ValidationError({"retired_at": "La date de retrait est contrôlée par le service métier."})
                if previous["status"] != self.status:
                    allowed = getattr(self, "_allow_status_transition", False) and (
                        (previous["status"] == PlanVersionStatus.DRAFT and self.status == PlanVersionStatus.PUBLISHED)
                        or (previous["status"] == PlanVersionStatus.PUBLISHED and self.status == PlanVersionStatus.RETIRED)
                    )
                    if not allowed:
                        raise ValidationError({"status": "Publication et retrait passent par les services métier."})
        self.full_clean()
        result = super().save(*args, **kwargs)
        self._allow_status_transition = False
        return result

    def delete(self, *args, **kwargs):
        status = type(self).objects.filter(pk=self.pk).values_list("status", flat=True).first()
        if status and status != PlanVersionStatus.DRAFT:
            raise ValidationError("Une PlanVersion publiée ou retirée ne peut pas être supprimée.")
        return super().delete(*args, **kwargs)

    def __str__(self):
        return f"{self.plan.code} v{self.version}"


def _assert_draft(plan_version_id):
    status = PlanVersion.objects.filter(pk=plan_version_id).values_list("status", flat=True).first()
    if status and status != PlanVersionStatus.DRAFT:
        raise ValidationError("Le contenu d'une PlanVersion publiée ou retirée est immuable.")


class PlanContentQuerySet(models.QuerySet):
    def update(self, **kwargs):
        if self.exclude(plan_version__status=PlanVersionStatus.DRAFT).exists():
            raise ValidationError("Le contenu d'une PlanVersion publiée ou retirée est immuable.")
        return super().update(**kwargs)

    def delete(self):
        if self.exclude(plan_version__status=PlanVersionStatus.DRAFT).exists():
            raise ValidationError("Le contenu d'une PlanVersion publiée ou retirée est immuable.")
        return super().delete()


class PlanBenefit(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    plan_version = models.ForeignKey(PlanVersion, on_delete=models.CASCADE, related_name="benefits")
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=80, blank=True)
    position = models.PositiveIntegerField(default=0)
    is_highlighted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = PlanContentQuerySet.as_manager()

    class Meta:
        ordering = ["plan_version", "position", "created_at", "id"]
        constraints = [models.UniqueConstraint(fields=["plan_version", "position"], name="subs_benefit_position_unique")]

    def save(self, *args, **kwargs):
        _assert_draft(self.plan_version_id)
        if self.pk and not self._state.adding:
            previous_id = type(self).objects.filter(pk=self.pk).values_list("plan_version_id", flat=True).first()
            if previous_id and previous_id != self.plan_version_id:
                _assert_draft(previous_id)
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        _assert_draft(self.plan_version_id)
        return super().delete(*args, **kwargs)

    def __str__(self):
        return self.title


class PlanEntitlement(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    plan_version = models.ForeignKey(PlanVersion, on_delete=models.CASCADE, related_name="entitlements")
    feature = models.ForeignKey(FeatureDefinition, on_delete=models.PROTECT, related_name="plan_entitlements")
    value = models.JSONField(encoder=DjangoJSONEncoder)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = PlanContentQuerySet.as_manager()

    class Meta:
        ordering = ["plan_version", "feature__code"]
        constraints = [models.UniqueConstraint(fields=["plan_version", "feature"], name="subs_plan_feature_unique")]
        indexes = [models.Index(fields=["feature", "plan_version"], name="subs_entitlement_lookup_idx")]

    def clean(self):
        super().clean()
        errors = {}
        if self.feature_id and self.plan_version_id:
            if not self.feature.is_active:
                errors["feature"] = "Une Feature inactive ne peut pas entrer dans une nouvelle configuration."
            elif not self.feature.supports_subject_type(self.plan_version.plan.subject_type):
                errors["feature"] = "La Feature ne supporte pas le type de sujet de ce Plan."
            else:
                try:
                    self.value = self.feature.normalize_entitlement_value(self.value)
                except ValidationError as exc:
                    errors.update(exc.message_dict)
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        _assert_draft(self.plan_version_id)
        if self.pk and not self._state.adding:
            previous_id = type(self).objects.filter(pk=self.pk).values_list("plan_version_id", flat=True).first()
            if previous_id and previous_id != self.plan_version_id:
                _assert_draft(previous_id)
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        _assert_draft(self.plan_version_id)
        return super().delete(*args, **kwargs)

    def __str__(self):
        return f"{self.plan_version} — {self.feature.code}"
