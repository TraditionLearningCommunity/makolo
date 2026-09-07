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


class ImmutableHistoryQuerySet(models.QuerySet):
    def update(self, **kwargs):
        if kwargs:
            raise ValidationError("L'historique Recognition est immuable ; ajoutez une écriture compensatrice.")
        return 0

    def delete(self):
        raise ValidationError("L'historique Recognition est immuable ; il ne peut pas être supprimé.")


class RecognitionAccount(models.Model):
    """Global Makolo Points account for exactly one Profile or one Space."""

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
    lifetime_earned = models.PositiveBigIntegerField(default=0)
    lifetime_spent = models.PositiveBigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(Q(profile__isnull=False, space__isnull=True) | Q(profile__isnull=True, space__isnull=False)),
                name="recognition_account_subject_xor",
            ),
            models.UniqueConstraint(
                fields=["profile"],
                condition=Q(profile__isnull=False),
                name="recognition_account_profile_unique",
            ),
            models.UniqueConstraint(
                fields=["space"],
                condition=Q(space__isnull=False),
                name="recognition_account_space_unique",
            ),
        ]

    @property
    def subject(self):
        return self.profile if self.profile_id else self.space

    @property
    def subject_type(self):
        return "profile" if self.profile_id else "space" if self.space_id else None

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
    """Scheduler watermark; windows are cadence, never the source of Points truth."""

    key = models.CharField(max_length=80, primary_key=True)
    policy_version = models.CharField(max_length=80)
    window_size_hours = models.PositiveSmallIntegerField(default=24)
    last_completed_end = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(window_size_hours__gte=1, window_size_hours__lte=168),
                name="recognition_cursor_window_hours_valid",
            )
        ]

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
            models.UniqueConstraint(
                fields=["cursor", "starts_at", "ends_at"],
                name="recognition_window_cursor_bounds_unique",
            ),
            models.CheckConstraint(condition=Q(ends_at__gt=F("starts_at")), name="recognition_window_order_valid"),
            models.CheckConstraint(
                condition=Q(pool_points=F("issued_points") + F("unattributed_points")),
                name="recognition_window_points_conserved",
            ),
        ]
        indexes = [models.Index(fields=["cursor", "status", "ends_at"], name="recognition_window_status_idx")]

    def __str__(self):
        return f"Recognition {self.cursor_id} {self.starts_at.isoformat()} → {self.ends_at.isoformat()} [{self.status}]"


class RecognitionAccrual(models.Model):
    """Cumulative impact bucket that prevents slice-frequency inflation.

    Small useful FLOW deltas can accumulate here until the policy's cumulative
    target advances by at least one Point. A new policy version starts a new
    accrual lineage; already granted Points are never repriced.
    """

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
            models.UniqueConstraint(
                fields=["accrual_key", "policy_version"],
                name="recognition_accrual_key_policy_unique",
            ),
            models.CheckConstraint(condition=Q(cumulative_impact__gte=0), name="recognition_accrual_impact_nonnegative"),
        ]
        indexes = [models.Index(fields=["channel", "updated_at"], name="recognition_accrual_channel_idx")]

    def __str__(self):
        return f"{self.accrual_key} — {self.cumulative_impact} → {self.matured_points} pts"


class RecognitionSliceReceipt(models.Model):
    """Immutable receipt proving one impact slice has already been consumed."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    window = models.ForeignKey(
        RecognitionEvaluationWindow,
        on_delete=models.PROTECT,
        related_name="slice_receipts",
    )
    accrual = models.ForeignKey(
        RecognitionAccrual,
        on_delete=models.PROTECT,
        related_name="slice_receipts",
    )
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
            models.CheckConstraint(condition=Q(impact_delta__gte=0), name="recognition_slice_impact_nonnegative"),
            models.CheckConstraint(
                condition=Q(pool_points=F("issued_points") + F("unattributed_points")),
                name="recognition_slice_points_conserved",
            ),
        ]
        indexes = [
            models.Index(fields=["window", "available_at"], name="recognition_slice_window_idx"),
            models.Index(fields=["channel", "occurred_at"], name="recognition_slice_channel_idx"),
        ]

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding:
            raise ValidationError("Un reçu Recognition est historique et ne peut pas être modifié.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Un reçu Recognition est historique et ne peut pas être supprimé.")

    def __str__(self):
        return f"{self.slice_key} — {self.pool_points} pts"


class RecognitionLedgerEntry(models.Model):
    """Immutable signed Points audit trail. Account balances are projections."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(
        RecognitionAccount,
        on_delete=models.PROTECT,
        related_name="ledger_entries",
    )
    kind = models.CharField(max_length=16, choices=LEDGER_KIND_CHOICES)
    points = models.BigIntegerField()
    description = models.CharField(max_length=255)
    idempotency_key = models.CharField(max_length=220, unique=True)
    recognized_slice = models.ForeignKey(
        RecognitionSliceReceipt,
        on_delete=models.PROTECT,
        related_name="ledger_entries",
        null=True,
        blank=True,
    )
    policy_version = models.CharField(max_length=80, blank=True)
    actor_profile = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="recognition_ledger_actions",
        null=True,
        blank=True,
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = ImmutableHistoryQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [models.CheckConstraint(condition=~Q(points=0), name="recognition_ledger_points_nonzero")]
        indexes = [
            models.Index(fields=["account", "created_at"], name="recognition_ledger_account_idx"),
            models.Index(fields=["kind", "created_at"], name="recognition_ledger_kind_idx"),
        ]

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding:
            raise ValidationError("Le ledger Recognition est immuable ; utilisez une écriture compensatrice.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Le ledger Recognition est immuable ; utilisez une écriture compensatrice.")

    def __str__(self):
        return f"{self.account_id} — {self.points:+d}"
