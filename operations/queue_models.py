import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone


class QueueStatus(models.TextChoices):
    OPEN = "open", "Ouverte"
    PAUSED = "paused", "En pause"
    CLOSED = "closed", "Fermée"


class QueueEntryStatus(models.TextChoices):
    WAITING = "waiting", "En attente"
    CALLED = "called", "Appelé"
    SERVED = "served", "Servi"
    EXPIRED = "expired", "Expiré"
    CANCELLED = "cancelled", "Annulé"


ACTIVE_QUEUE_ENTRY_STATUSES = (QueueEntryStatus.WAITING, QueueEntryStatus.CALLED)


class OccurrenceQueue(models.Model):
    """Live operational queue for one Occurrence. It is not a ticket Waitlist."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    occurrence = models.ForeignKey(
        "activities.Occurrence",
        on_delete=models.CASCADE,
        related_name="operational_queues",
    )
    checkpoint = models.ForeignKey(
        "operations.OccurrenceCheckpoint",
        on_delete=models.PROTECT,
        related_name="queues",
        null=True,
        blank=True,
    )
    key = models.CharField(max_length=80)
    label = models.CharField(max_length=180)
    status = models.CharField(max_length=16, choices=QueueStatus.choices, default=QueueStatus.OPEN)
    next_sequence = models.PositiveBigIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "operations"
        ordering = ["occurrence_id", "label", "id"]
        constraints = [
            models.UniqueConstraint(fields=["occurrence", "key"], name="ops_queue_occ_key_uq"),
        ]
        indexes = [
            models.Index(fields=["occurrence", "status"], name="ops_queue_occ_status_idx"),
        ]

    def clean(self):
        super().clean()
        self.key = (self.key or "").strip()
        self.label = (self.label or "").strip()
        errors = {}
        if not self.key:
            errors["key"] = "La clé de queue est obligatoire."
        if not self.label:
            errors["label"] = "Le libellé de queue est obligatoire."
        if self.checkpoint_id and self.checkpoint.occurrence_id != self.occurrence_id:
            errors["checkpoint"] = "Le checkpoint doit appartenir à la même Occurrence que la queue."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class QueueEntry(models.Model):
    """One beneficiary's live place in an OccurrenceQueue."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    queue = models.ForeignKey(OccurrenceQueue, on_delete=models.PROTECT, related_name="entries")
    profile = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="operational_queue_entries",
        null=True,
        blank=True,
    )
    external_beneficiary = models.ForeignKey(
        "journeys.ExternalBeneficiary",
        on_delete=models.PROTECT,
        related_name="operational_queue_entries",
        null=True,
        blank=True,
    )
    sequence = models.PositiveBigIntegerField()
    status = models.CharField(max_length=16, choices=QueueEntryStatus.choices, default=QueueEntryStatus.WAITING)
    source = models.CharField(max_length=80, blank=True)
    client_reference = models.CharField(max_length=64, blank=True)
    entered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="queue_entries_entered",
    )
    entered_at = models.DateTimeField(default=timezone.now)
    called_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="queue_entries_called",
        null=True,
        blank=True,
    )
    called_at = models.DateTimeField(null=True, blank=True)
    served_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="queue_entries_served",
        null=True,
        blank=True,
    )
    served_at = models.DateTimeField(null=True, blank=True)
    ended_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="queue_entries_ended",
        null=True,
        blank=True,
    )
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "operations"
        ordering = ["queue_id", "sequence", "id"]
        constraints = [
            models.CheckConstraint(
                condition=(Q(profile__isnull=False) & Q(external_beneficiary__isnull=True))
                | (Q(profile__isnull=True) & Q(external_beneficiary__isnull=False)),
                name="ops_queue_entry_subject_ck",
            ),
            models.UniqueConstraint(fields=["queue", "sequence"], name="ops_queue_entry_seq_uq"),
            models.UniqueConstraint(
                fields=["queue", "profile"],
                condition=Q(profile__isnull=False, status__in=ACTIVE_QUEUE_ENTRY_STATUSES),
                name="ops_queue_active_profile_uq",
            ),
            models.UniqueConstraint(
                fields=["queue", "external_beneficiary"],
                condition=Q(external_beneficiary__isnull=False, status__in=ACTIVE_QUEUE_ENTRY_STATUSES),
                name="ops_queue_active_ext_uq",
            ),
            models.UniqueConstraint(
                fields=["queue", "entered_by", "source", "client_reference"],
                condition=~Q(source="") & ~Q(client_reference=""),
                name="ops_queue_entry_client_uq",
            ),
        ]
        indexes = [
            models.Index(fields=["queue", "status", "sequence"], name="ops_queue_entry_fifo_idx"),
            models.Index(fields=["profile", "status"], name="ops_queue_entry_prof_idx"),
            models.Index(fields=["external_beneficiary", "status"], name="ops_queue_entry_ext_idx"),
        ]

    def clean(self):
        super().clean()
        if bool(self.profile_id) == bool(self.external_beneficiary_id):
            raise ValidationError({"profile": "Une QueueEntry doit viser exactement un Profile ou un ExternalBeneficiary."})
        if self.status == QueueEntryStatus.CALLED and not self.called_at:
            raise ValidationError({"called_at": "Un appel doit avoir un horodatage."})
        if self.status == QueueEntryStatus.SERVED and not self.served_at:
            raise ValidationError({"served_at": "Un service terminé doit avoir un horodatage."})
        if self.status in {QueueEntryStatus.EXPIRED, QueueEntryStatus.CANCELLED} and not self.ended_at:
            raise ValidationError({"ended_at": "Une entrée terminée doit avoir un horodatage."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    @property
    def is_active(self):
        return self.status in ACTIVE_QUEUE_ENTRY_STATUSES
