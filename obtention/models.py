import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q


class ObtentionModeCode(models.TextChoices):
    BUY = "buy", "Achat"
    RENT = "rent", "Location"
    BORROW = "borrow", "Emprunt"
    RECEIVE = "receive", "Réception / attribution"
    EXCHANGE = "exchange", "Échange"
    OTHER = "other", "Autre"


class FulfillmentTargetRule(models.TextChoices):
    ALL = "all", "Toutes les cibles"
    ANY = "any", "Au moins une cible"
    AT_LEAST_N = "at_least_n", "Au moins N cibles"


class ObtentionConfigurationStatus(models.TextChoices):
    DRAFT = "draft", "Brouillon"
    PUBLISHED = "published", "Publiée"
    RETIRED = "retired", "Retirée"


class ObtentionDetails(models.Model):
    """Vertical identity for one generic Activity.

    Mutable business configuration is versioned separately so an active
    beneficiary Journey never changes meaning retroactively.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    activity = models.OneToOneField(
        "activities.Activity",
        on_delete=models.CASCADE,
        related_name="obtention_details",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["activity__title", "id"]

    def __str__(self):
        return f"Obtention — {self.activity}"


class ObtentionConfiguration(models.Model):
    obtention = models.ForeignKey(
        ObtentionDetails,
        on_delete=models.CASCADE,
        related_name="configurations",
    )
    version = models.PositiveIntegerField(default=1)
    status = models.CharField(
        max_length=16,
        choices=ObtentionConfigurationStatus.choices,
        default=ObtentionConfigurationStatus.DRAFT,
    )
    result_label = models.CharField(
        max_length=220,
        help_text="Résultat réel permettant de dire que l'obtention est accomplie.",
    )
    target_rule = models.CharField(
        max_length=16,
        choices=FulfillmentTargetRule.choices,
        default=FulfillmentTargetRule.ALL,
    )
    minimum_targets = models.PositiveSmallIntegerField(null=True, blank=True)
    beneficiary_confirmation_required = models.BooleanField(default=True)
    operator_confirmation_required = models.BooleanField(default=False)
    journey_plan_template = models.ForeignKey(
        "journeys.JourneyPlanTemplate",
        on_delete=models.PROTECT,
        related_name="obtention_configurations",
        null=True,
        blank=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_obtention_configurations",
        null=True,
        blank=True,
    )
    published_at = models.DateTimeField(null=True, blank=True)
    retired_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["obtention", "-version", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["obtention", "version"],
                name="obtention_configuration_version_unique",
            ),
            models.CheckConstraint(
                condition=Q(version__gt=0),
                name="obtention_configuration_version_positive",
            ),
            models.CheckConstraint(
                condition=Q(minimum_targets__isnull=True) | Q(minimum_targets__gt=0),
                name="obtention_min_targets_positive",
            ),
            models.UniqueConstraint(
                fields=["obtention"],
                condition=Q(status=ObtentionConfigurationStatus.PUBLISHED),
                name="obtention_one_published_configuration",
            ),
        ]

    def clean(self):
        super().clean()
        self.result_label = (self.result_label or "").strip()
        errors = {}
        if not self.result_label:
            errors["result_label"] = "Définissez le résultat réel qui signifie « obtenu »."
        if self.target_rule == FulfillmentTargetRule.AT_LEAST_N:
            if not self.minimum_targets or self.minimum_targets < 1:
                errors["minimum_targets"] = "La règle « au moins N » exige une valeur strictement positive."
        elif self.minimum_targets is not None:
            errors["minimum_targets"] = "Le nombre minimal ne s'applique qu'à la règle « au moins N »."
        if self.journey_plan_template_id and self.obtention_id:
            if self.journey_plan_template.activity_id != self.obtention.activity_id:
                errors["journey_plan_template"] = "Le plan Journey doit appartenir à l'Activity Obtention."
            if self.journey_plan_template.status != "published":
                errors["journey_plan_template"] = "Le plan Journey pinné doit être publié."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.result_label = (self.result_label or "").strip()
        if self.pk and not self._state.adding:
            previous = ObtentionConfiguration.objects.filter(pk=self.pk).values(
                "obtention_id",
                "version",
                "status",
                "result_label",
                "target_rule",
                "minimum_targets",
                "beneficiary_confirmation_required",
                "operator_confirmation_required",
                "journey_plan_template_id",
            ).first()
            if previous and previous["status"] in {
                ObtentionConfigurationStatus.PUBLISHED,
                ObtentionConfigurationStatus.RETIRED,
            }:
                structural = {
                    "obtention_id": self.obtention_id,
                    "version": self.version,
                    "result_label": self.result_label,
                    "target_rule": self.target_rule,
                    "minimum_targets": self.minimum_targets,
                    "beneficiary_confirmation_required": self.beneficiary_confirmation_required,
                    "operator_confirmation_required": self.operator_confirmation_required,
                    "journey_plan_template_id": self.journey_plan_template_id,
                }
                if any(previous[name] != value for name, value in structural.items()):
                    raise ValidationError("Une configuration Obtention publiée est structurellement immuable.")
                allowed_statuses = {
                    ObtentionConfigurationStatus.PUBLISHED,
                    ObtentionConfigurationStatus.RETIRED,
                }
                if self.status not in allowed_statuses:
                    raise ValidationError("Une configuration publiée peut seulement rester publiée ou être retirée.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.status != ObtentionConfigurationStatus.DRAFT:
            raise ValidationError("Une configuration Obtention publiée ou retirée ne peut pas être supprimée.")
        return super().delete(*args, **kwargs)

    def __str__(self):
        return f"{self.obtention.activity} — v{self.version}"


class ObtentionConfigurationRequirementLink(models.Model):
    """Composition link; the Requirement truth remains owned by requirements."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    configuration = models.ForeignKey(
        ObtentionConfiguration,
        on_delete=models.CASCADE,
        related_name="requirement_links",
    )
    requirement = models.ForeignKey(
        "requirements.RequirementDefinition",
        on_delete=models.PROTECT,
        related_name="obtention_configuration_links",
    )
    step_key = models.SlugField(
        max_length=120,
        blank=True,
        help_text="Clé optionnelle d'une JourneyPlanTemplateStep qui matérialise l'action de satisfaction.",
    )
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["configuration", "position", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["configuration", "requirement"],
                name="obtention_requirement_link_unique",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.configuration_id:
            if self.configuration.status != ObtentionConfigurationStatus.DRAFT:
                errors["configuration"] = "Les Requirements d'une configuration publiée sont immuables."
            if self.requirement_id:
                if self.requirement.activity_id != self.configuration.obtention.activity_id:
                    errors["requirement"] = "Le Requirement doit appartenir à la même Activity."
                if self.requirement.status != "published":
                    errors["requirement"] = "Le Requirement lié doit être publié."
        if self.step_key and self.configuration_id:
            template = self.configuration.journey_plan_template
            if template is None or not template.steps.filter(key=self.step_key).exists():
                errors["step_key"] = "La Step de satisfaction n'existe pas dans le plan pinné."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


def _configuration_is_editable(configuration_id):
    if not configuration_id:
        return True
    status = (
        ObtentionConfiguration.objects.filter(pk=configuration_id)
        .values_list("status", flat=True)
        .first()
    )
    return status in {None, ObtentionConfigurationStatus.DRAFT}


class ObtentionTarget(models.Model):
    """What must actually be obtained; intentionally distinct from Commerce Offer."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    configuration = models.ForeignKey(
        ObtentionConfiguration,
        on_delete=models.CASCADE,
        related_name="targets",
    )
    title = models.CharField(max_length=220)
    description = models.TextField(blank=True)
    characteristics = models.JSONField(default=dict, blank=True)
    quantity = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        default=Decimal("1"),
        validators=[MinValueValidator(Decimal("0.001"))],
    )
    unit = models.CharField(max_length=40, blank=True)
    position = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["position", "created_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(quantity__gt=0),
                name="obtention_target_quantity_positive",
            ),
        ]
        indexes = [
            models.Index(
                fields=["configuration", "position"],
                name="obtention_target_order_idx",
            ),
        ]

    def clean(self):
        super().clean()
        self.title = (self.title or "").strip()
        self.description = (self.description or "").strip()
        self.unit = (self.unit or "").strip()
        errors = {}
        if not self.title:
            errors["title"] = "La cible doit avoir un intitulé."
        if self.quantity is None or self.quantity <= 0:
            errors["quantity"] = "La quantité cible doit être strictement positive."
        if self.configuration_id and not _configuration_is_editable(self.configuration_id):
            errors["configuration"] = "Les cibles d'une configuration publiée ou retirée sont immuables."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if not _configuration_is_editable(self.configuration_id):
            raise ValidationError("Les cibles d'une configuration publiée ou retirée sont immuables.")
        return super().delete(*args, **kwargs)

    def __str__(self):
        suffix = f" {self.unit}" if self.unit else ""
        return f"{self.quantity:g}{suffix} — {self.title}"


class ObtentionMode(models.Model):
    """One admissible relation of obtaining for a configuration."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    configuration = models.ForeignKey(
        ObtentionConfiguration,
        on_delete=models.CASCADE,
        related_name="modes",
    )
    code = models.CharField(max_length=16, choices=ObtentionModeCode.choices)
    label = models.CharField(
        max_length=120,
        blank=True,
        help_text="Libellé métier optionnel lorsque le contexte exige plus de précision.",
    )
    position = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["position", "created_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["configuration", "code"],
                name="obtention_mode_unique",
            ),
        ]

    def clean(self):
        super().clean()
        self.label = (self.label or "").strip()
        if self.configuration_id and not _configuration_is_editable(self.configuration_id):
            raise ValidationError({"configuration": "Les modes d'une configuration publiée ou retirée sont immuables."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if not _configuration_is_editable(self.configuration_id):
            raise ValidationError("Les modes d'une configuration publiée ou retirée sont immuables.")
        return super().delete(*args, **kwargs)

    def __str__(self):
        return self.label or self.get_code_display()


class ObtentionJourneyContext(models.Model):
    """Pins one Journey to the exact Obtention contract and chosen mode."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    journey = models.OneToOneField(
        "journeys.Journey",
        on_delete=models.CASCADE,
        related_name="obtention_context",
    )
    configuration = models.ForeignKey(
        ObtentionConfiguration,
        on_delete=models.PROTECT,
        related_name="journey_contexts",
    )
    mode = models.ForeignKey(
        ObtentionMode,
        on_delete=models.PROTECT,
        related_name="journey_contexts",
    )
    plan_materialized_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "id"]

    def clean(self):
        super().clean()
        errors = {}
        if self.configuration_id and self.configuration.status != ObtentionConfigurationStatus.PUBLISHED:
            errors["configuration"] = "Une Journey Obtention doit pinner une configuration publiée."
        if self.mode_id and self.configuration_id and self.mode.configuration_id != self.configuration_id:
            errors["mode"] = "Le mode doit appartenir à la configuration pinnée."
        if self.journey_id and self.configuration_id:
            if self.journey.activity_id != self.configuration.obtention.activity_id:
                errors["journey"] = "La Journey et la configuration doivent appartenir à la même Activity."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding:
            previous = ObtentionJourneyContext.objects.filter(pk=self.pk).values(
                "journey_id", "configuration_id", "mode_id"
            ).first()
            current = {
                "journey_id": self.journey_id,
                "configuration_id": self.configuration_id,
                "mode_id": self.mode_id,
            }
            if previous and previous != current:
                raise ValidationError("Le contrat et le mode pinnés d'une Journey Obtention sont immuables.")
        self.full_clean()
        return super().save(*args, **kwargs)


class ObtentionTargetReceipt(models.Model):
    """Observed target quantity and confirmations for one Journey."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    journey = models.ForeignKey(
        "journeys.Journey",
        on_delete=models.CASCADE,
        related_name="obtention_target_receipts",
    )
    target = models.ForeignKey(
        ObtentionTarget,
        on_delete=models.PROTECT,
        related_name="receipts",
    )
    received_quantity = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    beneficiary_confirmed_at = models.DateTimeField(null=True, blank=True)
    operator_confirmed_at = models.DateTimeField(null=True, blank=True)
    operator_confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="confirmed_obtention_receipts",
        null=True,
        blank=True,
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="updated_obtention_receipts",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["target__position", "target_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["journey", "target"],
                name="obtention_receipt_target_unique",
            ),
            models.CheckConstraint(
                condition=Q(received_quantity__gte=0),
                name="obtention_receipt_quantity_nonnegative",
            ),
        ]
        indexes = [
            models.Index(
                fields=["journey", "target"],
                name="obtention_receipt_journey_idx",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.received_quantity is None or self.received_quantity < 0:
            errors["received_quantity"] = "La quantité reçue ne peut pas être négative."
        if self.journey_id and self.target_id:
            try:
                context = self.journey.obtention_context
            except ObtentionJourneyContext.DoesNotExist:
                errors["journey"] = "La Journey n'a pas de contexte Obtention."
            else:
                if self.target.configuration_id != context.configuration_id:
                    errors["target"] = "La cible doit appartenir à la configuration pinnée de cette Journey."
        if self.operator_confirmed_at and not self.operator_confirmed_by_id:
            errors["operator_confirmed_by"] = "Une confirmation du porteur doit identifier son auteur."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding:
            previous = ObtentionTargetReceipt.objects.filter(pk=self.pk).values(
                "journey_id", "target_id"
            ).first()
            if previous and (
                previous["journey_id"] != self.journey_id
                or previous["target_id"] != self.target_id
            ):
                raise ValidationError("L'identité d'un constat d'obtention est immuable.")
        self.full_clean()
        return super().save(*args, **kwargs)
