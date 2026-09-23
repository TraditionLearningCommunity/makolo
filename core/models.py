import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class DomainEventStatus(models.TextChoices):
    PENDING = "pending", "En attente"
    PROCESSING = "processing", "En cours"
    PROCESSED = "processed", "Traité"
    FAILED = "failed", "Échoué"


class DomainEventConsumptionStatus(models.TextChoices):
    PENDING = "pending", "En attente"
    PROCESSING = "processing", "En cours"
    PROCESSED = "processed", "Traité"
    SKIPPED = "skipped", "Ignoré"
    FAILED = "failed", "Échoué"


DOMAIN_EVENT_FACT_FIELDS = frozenset({
    "event_type",
    "source_type",
    "source_id",
    "space_id",
    "activity_id",
    "payload_version",
    "payload",
    "occurred_at",
    "created_at",
    "idempotency_key",
})


class DomainEventOutboxQuerySet(models.QuerySet):
    """Protect the immutable fact while allowing delivery bookkeeping to advance."""

    def update(self, **kwargs):
        protected = DOMAIN_EVENT_FACT_FIELDS.intersection(kwargs)
        if protected:
            names = ", ".join(sorted(protected))
            raise ValidationError(
                f"Un Domain Event persisté est immuable; champs interdits: {names}."
            )
        return super().update(**kwargs)

    def bulk_update(self, objs, fields, batch_size=None):
        protected = DOMAIN_EVENT_FACT_FIELDS.intersection(fields)
        if protected:
            names = ", ".join(sorted(protected))
            raise ValidationError(
                f"Un Domain Event persisté est immuable; champs interdits: {names}."
            )
        return super().bulk_update(objs, fields, batch_size=batch_size)


class DomainEventOutbox(models.Model):
    """Immutable domain fact plus mutable delivery bookkeeping."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_type = models.CharField(max_length=100)
    source_type = models.CharField(max_length=80)
    source_id = models.CharField(max_length=128, blank=True)
    space_id = models.UUIDField(null=True, blank=True)
    activity_id = models.UUIDField(null=True, blank=True)
    payload_version = models.PositiveSmallIntegerField(default=1)
    payload = models.JSONField(default=dict, blank=True)
    occurred_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.CharField(
        max_length=16,
        choices=DomainEventStatus.choices,
        default=DomainEventStatus.PENDING,
    )
    attempts = models.PositiveSmallIntegerField(default=0)
    max_attempts = models.PositiveSmallIntegerField(default=5)
    claimed_at = models.DateTimeField(null=True, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    idempotency_key = models.CharField(max_length=255, unique=True)

    objects = DomainEventOutboxQuerySet.as_manager()

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [
            models.Index(fields=["status", "created_at"], name="de_outbox_status_created_idx"),
            models.Index(fields=["event_type", "created_at"], name="de_outbox_type_created_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(payload_version__gt=0),
                name="de_outbox_payload_version_pos",
            ),
            models.CheckConstraint(
                condition=models.Q(max_attempts__gt=0),
                name="de_outbox_max_attempts_pos",
            ),
        ]

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding:
            update_fields = kwargs.get("update_fields")
            protected = set(DOMAIN_EVENT_FACT_FIELDS)
            if update_fields is not None:
                protected.intersection_update(update_fields)
            if protected:
                names = sorted(protected)
                persisted = (
                    type(self)._base_manager.filter(pk=self.pk)
                    .values(*names)
                    .first()
                )
                if persisted is not None:
                    changed = [
                        name
                        for name in names
                        if persisted[name] != getattr(self, name)
                    ]
                    if changed:
                        raise ValidationError(
                            "Un Domain Event persisté est immuable; "
                            f"champs modifiés: {', '.join(changed)}."
                        )
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.event_type} — {self.source_type}:{self.source_id or self.id}"


class DomainEventConsumption(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(
        DomainEventOutbox,
        on_delete=models.CASCADE,
        related_name="consumptions",
    )
    consumer = models.CharField(max_length=100)
    status = models.CharField(
        max_length=16,
        choices=DomainEventConsumptionStatus.choices,
        default=DomainEventConsumptionStatus.PENDING,
    )
    attempts = models.PositiveSmallIntegerField(default=0)
    max_attempts = models.PositiveSmallIntegerField(default=5)
    processed_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["event_id", "consumer"]
        constraints = [
            models.UniqueConstraint(
                fields=["event", "consumer"],
                name="de_consumption_event_consumer_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(max_attempts__gt=0),
                name="de_consumption_max_attempts_pos",
            ),
        ]
        indexes = [
            models.Index(fields=["event", "status"], name="de_consumer_event_status_idx"),
            models.Index(fields=["consumer", "status"], name="de_consumer_name_status_idx"),
        ]

    def __str__(self):
        return f"{self.event_id} — {self.consumer} — {self.status}"
