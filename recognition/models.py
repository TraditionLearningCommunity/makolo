from __future__ import annotations

import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q

from .contracts import ImpactChannel, RecognitionLedgerKind, RecognitionWindowStatus, TemporalProfile


IMPACT_CHANNEL_CHOICES = [(item.value, item.value.replace("_", " ").title()) for item in ImpactChannel]
TEMPORAL_PROFILE_CHOICES = [(item.value, item.value.title()) for item in TemporalProfile]
WINDOW_STATUS_CHOICES = [(item.value, item.value.title()) for item in RecognitionWindowStatus]
LEDGER_KIND_CHOICES = [(item.value, item.value.title()) for item in RecognitionLedgerKind]


class PolicyStatus(models.TextChoices):
    DRAFT = "draft", "Brouillon"
    SIMULATED = "simulated", "Simulée"
    SCHEDULED = "scheduled", "Planifiée"
    ACTIVE = "active", "Active"
    SUPERSEDED = "superseded", "Remplacée"
    RETIRED = "retired", "Retirée"


class RuleCombination(models.TextChoices):
    ADDITIVE = "additive", "Additive"
    EXCLUSIVE = "exclusive", "Exclusive"
    MAX = "max", "Maximum"


class CausalMode(models.TextChoices):
    OPERATE = "operate", "Opérer"
    ORCHESTRATE = "orchestrate", "Orchestrer"
    DELIVER = "deliver", "Livrer"
    ENABLE = "enable", "Rendre possible"
    AMPLIFY = "amplify", "Amplifier"
    MAINTAIN = "maintain", "Maintenir"


class RewardKind(models.TextChoices):
    ENTITLEMENT = "entitlement", "Entitlement"
    PROMOTION = "promotion", "Promotion"
    ACCESS = "access", "Access"
    INTRODUCTION = "introduction", "Introduction"
    PAYOUT = "payout", "Payout"
    OTHER = "other", "Autre"


class RedemptionStatus(models.TextChoices):
    REQUESTED = "requested", "Demandée"
    FULFILLED = "fulfilled", "Réalisée"
    CANCELLED = "cancelled", "Annulée"


class ImmutableHistoryQuerySet(models.QuerySet):
    def update(self, **kwargs):
        if kwargs:
            raise ValidationError("L'historique Recognition est immuable ; ajoutez une écriture compensatrice.")
        return 0

    def delete(self):
        raise ValidationError("L'historique Recognition est immuable ; il ne peut pas être supprimé.")


class RecognitionPolicy(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.SlugField(max_length=100)
    version = models.PositiveIntegerField(default=1)
    name = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=PolicyStatus.choices, default=PolicyStatus.DRAFT)
    effective_from = models.DateTimeField(null=True, blank=True)
    effective_until = models.DateTimeField(null=True, blank=True)
    parameters = models.JSONField(default=dict, blank=True)
    standard_window_hours = models.PositiveSmallIntegerField(default=24)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["code", "-version"]
        constraints = [models.UniqueConstraint(fields=["code", "version"], name="rec_policy_code_ver_uq")]

    def clean(self):
        super().clean()
        if self.effective_from and self.effective_until and self.effective_until <= self.effective_from:
            raise ValidationError({"effective_until": "La fin doit être postérieure au début."})
        if not 1 <= self.standard_window_hours <= 168:
            raise ValidationError({"standard_window_hours": "La fenêtre doit être comprise entre 1 et 168 heures."})
        if self.pk:
            previous = RecognitionPolicy.objects.filter(pk=self.pk).first()
            if previous and previous.status in {PolicyStatus.ACTIVE, PolicyStatus.SUPERSEDED, PolicyStatus.RETIRED}:
                protected = (
                    "code", "version", "name", "description", "effective_from", "effective_until",
                    "parameters", "standard_window_hours",
                )
                if any(getattr(previous, field) != getattr(self, field) for field in protected):
                    raise ValidationError("Une Policy publiée est immuable. Clonez-la dans une nouvelle version.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.status not in {PolicyStatus.DRAFT, PolicyStatus.SIMULATED}:
            raise ValidationError("Une Policy publiée ne peut pas être supprimée.")
        return super().delete(*args, **kwargs)

    @property
    def version_key(self):
        return f"{self.code}:v{self.version}"

    def __str__(self):
        return f"{self.name} v{self.version}"


class RecognitionRule(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    policy = models.ForeignKey(RecognitionPolicy, on_delete=models.CASCADE, related_name="rules")
    code = models.SlugField(max_length=100)
    name = models.CharField(max_length=180)
    signal_kind = models.CharField(max_length=120)
    channel = models.CharField(max_length=24, choices=IMPACT_CHANNEL_CHOICES, default=ImpactChannel.ACTIONABILITY.value)
    scope = models.JSONField(default=dict, blank=True)
    conditions = models.JSONField(default=dict, blank=True)
    measure = models.JSONField(default=dict, blank=True)
    normalization = models.JSONField(default=dict, blank=True)
    temporal_profile = models.CharField(max_length=16, choices=TEMPORAL_PROFILE_CHOICES, default=TemporalProfile.PULSE.value)
    aggregation = models.CharField(max_length=32, default="SUM")
    curve = models.JSONField(default=dict, blank=True)
    modulators = models.JSONField(default=list, blank=True)
    outcome_identity = models.JSONField(default=dict, blank=True)
    attribution = models.JSONField(default=dict, blank=True)
    combination = models.CharField(max_length=20, choices=RuleCombination.choices, default=RuleCombination.ADDITIVE)
    priority = models.PositiveIntegerField(default=100)
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["priority", "code"]
        constraints = [models.UniqueConstraint(fields=["policy", "code"], name="rec_rule_policy_code_uq")]
        indexes = [models.Index(fields=["policy", "signal_kind", "enabled"], name="rec_rule_signal_idx")]

    def clean(self):
        super().clean()
        from .policy_dsl import validate_rule_definition
        validate_rule_definition(self)
        if self.pk:
            previous = RecognitionRule.objects.filter(pk=self.pk).select_related("policy").first()
            if previous and previous.policy.status not in {PolicyStatus.DRAFT, PolicyStatus.SIMULATED}:
                raise ValidationError("Les Rules d’une Policy publiée sont immuables. Clonez la Policy.")

    def save(self, *args, **kwargs):
        if self.policy_id and self.policy.status not in {PolicyStatus.DRAFT, PolicyStatus.SIMULATED} and not self._state.adding:
            raise ValidationError("Les Rules d’une Policy publiée sont immuables. Clonez la Policy.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.policy.status not in {PolicyStatus.DRAFT, PolicyStatus.SIMULATED}:
            raise ValidationError("Les Rules d’une Policy publiée ne peuvent pas être supprimées.")
        return super().delete(*args, **kwargs)

    def __str__(self):
        return f"{self.policy} — {self.name}"


class RecognitionSignal(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    signal_id = models.CharField(max_length=255, unique=True)
    signal_kind = models.CharField(max_length=120, db_index=True)
    object_type = models.CharField(max_length=120)
    object_id = models.CharField(max_length=160)
    occurred_at = models.DateTimeField()
    available_at = models.DateTimeField(db_index=True)
    outcome_identity = models.CharField(max_length=255)
    values = models.JSONField(default=dict, blank=True)
    contributors = models.JSONField(default=list, blank=True)
    confidence = models.DecimalField(max_digits=8, decimal_places=6, default=Decimal("1"))
    source_ref = models.CharField(max_length=255, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["available_at", "created_at"]
        constraints = [models.UniqueConstraint(fields=["signal_kind", "outcome_identity"], name="rec_signal_outcome_uq")]
        indexes = [models.Index(fields=["processed_at", "available_at"], name="rec_signal_pending_idx")]

    def clean(self):
        super().clean()
        if not Decimal("0") <= self.confidence <= Decimal("1"):
            raise ValidationError({"confidence": "La confiance doit être comprise entre 0 et 1."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class RecognitionAccount(models.Model):
    """Global Makolo credits account for exactly one Profile or one Space."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="recognition_accounts",
        null=True,
        blank=True,
    )
    space = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="recognition_accounts",
        null=True,
        blank=True,
    )
    points_balance = models.PositiveBigIntegerField(default=0)
    pending_points = models.PositiveBigIntegerField(default=0)
    correction_deficit = models.PositiveBigIntegerField(default=0)
    lifetime_earned = models.PositiveBigIntegerField(default=0)
    lifetime_spent = models.PositiveBigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(Q(profile__isnull=False, space__isnull=True) | Q(profile__isnull=True, space__isnull=False)),
                name="rec_account_subject_xor",
            ),
            models.UniqueConstraint(fields=["profile"], condition=Q(profile__isnull=False), name="rec_account_profile_unique"),
            models.UniqueConstraint(fields=["space"], condition=Q(space__isnull=False), name="rec_account_space_unique"),
        ]

    @property
    def subject(self):
        return self.profile if self.profile_id else self.space

    @property
    def subject_type(self):
        return "profile" if self.profile_id else "space" if self.space_id else None

    @property
    def available_credits(self):
        return self.points_balance

    def clean(self):
        super().clean()
        if bool(self.profile_id) == bool(self.space_id):
            raise ValidationError("Un compte Recognition appartient exactement à un Profile ou un Space.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"Recognition {self.subject_type}:{getattr(self.subject, 'pk', None)} — {self.points_balance}"


class RecognitionCursor(models.Model):
    """Scheduler watermark; windows are cadence, never the source of credits truth."""

    key = models.CharField(max_length=80, primary_key=True)
    policy_version = models.CharField(max_length=80)
    window_size_hours = models.PositiveSmallIntegerField(default=24)
    last_completed_end = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(window_size_hours__gte=1, window_size_hours__lte=168), name="rec_cursor_window_hours_valid")]

    def clean(self):
        super().clean()
        if not 1 <= self.window_size_hours <= 168:
            raise ValidationError({"window_size_hours": "La fenêtre doit être comprise entre 1 et 168 heures."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class RecognitionEvaluationWindow(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cursor = models.ForeignKey(RecognitionCursor, on_delete=models.PROTECT, related_name="evaluation_windows")
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    policy_version = models.CharField(max_length=80)
    status = models.CharField(max_length=16, choices=WINDOW_STATUS_CHOICES, default=RecognitionWindowStatus.PENDING.value)
    processed_slices = models.PositiveIntegerField(default=0)
    pool_points = models.PositiveBigIntegerField(default=0)
    issued_points = models.PositiveBigIntegerField(default=0)
    unattributed_points = models.PositiveBigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["starts_at", "id"]
        constraints = [
            models.UniqueConstraint(fields=["cursor", "starts_at", "ends_at"], name="rec_window_bounds_unique"),
            models.CheckConstraint(condition=Q(ends_at__gt=F("starts_at")), name="rec_window_order_valid"),
            models.CheckConstraint(condition=Q(pool_points=F("issued_points") + F("unattributed_points")), name="rec_window_points_conserved"),
        ]
        indexes = [models.Index(fields=["cursor", "status", "ends_at"], name="rec_window_status_idx")]

    def __str__(self):
        return f"Recognition {self.cursor_id} {self.starts_at.isoformat()} → {self.ends_at.isoformat()} [{self.status}]"


class RecognitionAccrual(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    accrual_key = models.CharField(max_length=220)
    policy_version = models.CharField(max_length=80)
    channel = models.CharField(max_length=24, choices=IMPACT_CHANNEL_CHOICES)
    cumulative_impact = models.DecimalField(max_digits=24, decimal_places=8, default=Decimal("0"))
    matured_points = models.PositiveBigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["accrual_key", "policy_version"], name="rec_accrual_key_policy_unique"),
            models.CheckConstraint(condition=Q(cumulative_impact__gte=0), name="rec_accrual_impact_nonneg"),
        ]
        indexes = [models.Index(fields=["channel", "updated_at"], name="rec_accrual_channel_idx")]

    def __str__(self):
        return f"{self.accrual_key} — {self.cumulative_impact} → {self.matured_points} pts"


class RecognitionSliceReceipt(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    window = models.ForeignKey(RecognitionEvaluationWindow, on_delete=models.PROTECT, related_name="slice_receipts")
    accrual = models.ForeignKey(RecognitionAccrual, on_delete=models.PROTECT, related_name="slice_receipts")
    slice_key = models.CharField(max_length=240, unique=True)
    policy_version = models.CharField(max_length=80)
    channel = models.CharField(max_length=24, choices=IMPACT_CHANNEL_CHOICES)
    temporal_profile = models.CharField(max_length=16, choices=TEMPORAL_PROFILE_CHOICES)
    occurred_at = models.DateTimeField()
    available_at = models.DateTimeField()
    impact_delta = models.DecimalField(max_digits=24, decimal_places=8)
    pool_points = models.PositiveBigIntegerField(default=0)
    issued_points = models.PositiveBigIntegerField(default=0)
    unattributed_points = models.PositiveBigIntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    objects = ImmutableHistoryQuerySet.as_manager()

    class Meta:
        ordering = ["available_at", "id"]
        constraints = [
            models.CheckConstraint(condition=Q(impact_delta__gte=0), name="rec_slice_impact_nonneg"),
            models.CheckConstraint(condition=Q(pool_points=F("issued_points") + F("unattributed_points")), name="rec_slice_points_conserved"),
        ]
        indexes = [
            models.Index(fields=["window", "available_at"], name="rec_slice_window_idx"),
            models.Index(fields=["channel", "occurred_at"], name="rec_slice_channel_idx"),
        ]

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding:
            raise ValidationError("Un reçu Recognition est historique et ne peut pas être modifié.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Un reçu Recognition est historique et ne peut pas être supprimé.")

    def __str__(self):
        return f"{self.slice_key} — {self.pool_points} pts"


class RecognitionObjectEvaluation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    window = models.ForeignKey(RecognitionEvaluationWindow, on_delete=models.PROTECT, related_name="object_evaluations")
    rule = models.ForeignKey(RecognitionRule, on_delete=models.PROTECT, null=True, blank=True, related_name="evaluations")
    receipt = models.OneToOneField(RecognitionSliceReceipt, on_delete=models.PROTECT, related_name="object_evaluation")
    object_type = models.CharField(max_length=120)
    object_id = models.CharField(max_length=160)
    utility_delta = models.DecimalField(max_digits=24, decimal_places=8)
    pool_points = models.PositiveBigIntegerField(default=0)
    unattributed_points = models.PositiveBigIntegerField(default=0)
    explanation = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    objects = ImmutableHistoryQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["object_type", "object_id", "created_at"], name="rec_eval_object_idx")]

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding:
            raise ValidationError("Une évaluation Recognition historique est immuable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Une évaluation Recognition historique est immuable.")


class RecognitionLedgerEntry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(RecognitionAccount, on_delete=models.PROTECT, related_name="ledger_entries")
    kind = models.CharField(max_length=16, choices=LEDGER_KIND_CHOICES)
    points = models.BigIntegerField()
    description = models.CharField(max_length=255)
    idempotency_key = models.CharField(max_length=220, unique=True)
    recognized_slice = models.ForeignKey(RecognitionSliceReceipt, on_delete=models.PROTECT, related_name="ledger_entries", null=True, blank=True)
    policy_version = models.CharField(max_length=80, blank=True)
    actor_profile = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="recognition_ledger_actions", null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    objects = ImmutableHistoryQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [models.CheckConstraint(condition=~Q(points=0), name="rec_ledger_points_nonzero")]
        indexes = [
            models.Index(fields=["account", "created_at"], name="rec_ledger_account_idx"),
            models.Index(fields=["kind", "created_at"], name="rec_ledger_kind_idx"),
        ]

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding:
            raise ValidationError("Le ledger Recognition est immuable ; utilisez une écriture compensatrice.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Le ledger Recognition est immuable ; utilisez une écriture compensatrice.")

    def __str__(self):
        return f"{self.account_id} — {self.points:+d}"


class RecognitionAllocation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    evaluation = models.ForeignKey(RecognitionObjectEvaluation, on_delete=models.PROTECT, related_name="allocations")
    account = models.ForeignKey(RecognitionAccount, on_delete=models.PROTECT, related_name="allocations")
    causal_mode = models.CharField(max_length=20, choices=CausalMode.choices, default=CausalMode.OPERATE)
    causal_strength = models.DecimalField(max_digits=18, decimal_places=10, default=Decimal("0"))
    share = models.DecimalField(max_digits=12, decimal_places=10, default=Decimal("0"))
    points = models.PositiveBigIntegerField(default=0)
    evidence = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    objects = ImmutableHistoryQuerySet.as_manager()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["evaluation", "account", "causal_mode"], name="rec_alloc_eval_acct_uq")]

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding:
            raise ValidationError("Une attribution Recognition historique est immuable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Une attribution Recognition historique est immuable.")


class AchievementDefinition(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.SlugField(max_length=100, unique=True)
    name = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    criteria = models.JSONField(default=dict, blank=True)
    badge_label = models.CharField(max_length=120, blank=True)
    is_active = models.BooleanField(default=True)
    is_publicly_presentable = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class AchievementGrant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    achievement = models.ForeignKey(AchievementDefinition, on_delete=models.PROTECT, related_name="grants")
    account = models.ForeignKey(RecognitionAccount, on_delete=models.PROTECT, related_name="achievement_grants")
    evaluation = models.ForeignKey(RecognitionObjectEvaluation, on_delete=models.PROTECT, null=True, blank=True, related_name="achievement_grants")
    idempotency_key = models.CharField(max_length=220, unique=True)
    evidence = models.JSONField(default=dict, blank=True)
    granted_at = models.DateTimeField(auto_now_add=True)
    objects = ImmutableHistoryQuerySet.as_manager()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["achievement", "account"], name="rec_ach_account_uq")]

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding:
            raise ValidationError("Un Achievement accordé est historique et immuable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Un Achievement accordé est historique et immuable.")


class RewardDefinition(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.SlugField(max_length=100)
    version = models.PositiveIntegerField(default=1)
    name = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    kind = models.CharField(max_length=20, choices=RewardKind.choices, default=RewardKind.OTHER)
    points_cost = models.PositiveBigIntegerField()
    fulfillment = models.JSONField(default=dict, blank=True)
    eligibility = models.JSONField(default=dict, blank=True)
    beneficiary_allowed = models.BooleanField(default=True)
    acceptance_required = models.BooleanField(default=False)
    stock = models.PositiveIntegerField(null=True, blank=True)
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_until = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "-version"]
        constraints = [models.UniqueConstraint(fields=["code", "version"], name="rec_reward_code_ver_uq")]

    def clean(self):
        super().clean()
        if self.points_cost < 1:
            raise ValidationError({"points_cost": "Une Reward doit coûter au moins un crédit."})
        if self.valid_from and self.valid_until and self.valid_until <= self.valid_from:
            raise ValidationError({"valid_until": "La fin doit être postérieure au début."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.points_cost} crédits)"


class RecognitionRedemption(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner_account = models.ForeignKey(RecognitionAccount, on_delete=models.PROTECT, related_name="redemptions")
    reward = models.ForeignKey(RewardDefinition, on_delete=models.PROTECT, related_name="redemptions")
    beneficiary_profile = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="recognition_benefits_received")
    beneficiary_space = models.ForeignKey("organizations.Organization", on_delete=models.PROTECT, null=True, blank=True, related_name="recognition_benefits_received")
    points_cost = models.PositiveBigIntegerField()
    status = models.CharField(max_length=20, choices=RedemptionStatus.choices, default=RedemptionStatus.REQUESTED)
    idempotency_key = models.CharField(max_length=220, unique=True)
    fulfillment_snapshot = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    fulfilled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.CheckConstraint(condition=(Q(beneficiary_profile__isnull=False, beneficiary_space__isnull=True) | Q(beneficiary_profile__isnull=True, beneficiary_space__isnull=False)), name="rec_redemption_benef_xor")]

    def clean(self):
        super().clean()
        if bool(self.beneficiary_profile_id) == bool(self.beneficiary_space_id):
            raise ValidationError("Une utilisation vise exactement un Profile ou un Space bénéficiaire.")
        if self.points_cost < 1:
            raise ValidationError({"points_cost": "Le coût doit être positif."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
