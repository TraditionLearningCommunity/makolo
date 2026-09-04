from __future__ import annotations

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone


class ProactivePreparationWatchKind(models.TextChoices):
    OPPORTUNITY = "opportunity", "Opportunity suivie"
    JOURNEY = "journey", "Démarche"


class ProactivePreparationCursor(models.Model):
    """Minimal operational memory for R3 previous-vs-current comparison.

    This row is not business truth and intentionally stores no contextual action
    payload, labels, requirements, proof details, filenames, hashes, or location.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="proactive_preparation_cursors",
    )
    watch_kind = models.CharField(max_length=20, choices=ProactivePreparationWatchKind.choices)
    opportunity_save = models.ForeignKey(
        "opportunities.OpportunitySave",
        on_delete=models.CASCADE,
        related_name="proactive_preparation_cursors",
        null=True,
        blank=True,
    )
    journey = models.ForeignKey(
        "journeys.Journey",
        on_delete=models.CASCADE,
        related_name="proactive_preparation_cursors",
        null=True,
        blank=True,
    )
    projection_signature = models.CharField(max_length=96)
    notification_signature = models.CharField(max_length=96)
    signature_version = models.CharField(max_length=40)
    transition_sequence = models.PositiveBigIntegerField(default=0)
    last_evaluated_at = models.DateTimeField(default=timezone.now)
    last_notified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "automation"
        ordering = ["last_evaluated_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(
                        watch_kind=ProactivePreparationWatchKind.OPPORTUNITY,
                        opportunity_save__isnull=False,
                        journey__isnull=True,
                    )
                    | Q(
                        watch_kind=ProactivePreparationWatchKind.JOURNEY,
                        opportunity_save__isnull=True,
                        journey__isnull=False,
                    )
                ),
                name="auto_prep_cursor_anchor_ck",
            ),
            models.UniqueConstraint(
                fields=["recipient", "opportunity_save"],
                condition=Q(opportunity_save__isnull=False),
                name="auto_prep_cursor_opp_unique",
            ),
            models.UniqueConstraint(
                fields=["recipient", "journey"],
                condition=Q(journey__isnull=False),
                name="auto_prep_cursor_journey_unique",
            ),
        ]
        indexes = [
            models.Index(fields=["last_evaluated_at", "id"], name="auto_prep_cursor_eval_idx"),
            models.Index(fields=["recipient", "watch_kind"], name="auto_prep_cursor_rec_idx"),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.watch_kind == ProactivePreparationWatchKind.OPPORTUNITY:
            if not self.opportunity_save_id or self.journey_id:
                errors["opportunity_save"] = "Un watch Opportunity exige uniquement OpportunitySave."
            elif self.opportunity_save.profile_id != self.recipient_id:
                errors["recipient"] = "Le recipient doit être le propriétaire de l’OpportunitySave."
        elif self.watch_kind == ProactivePreparationWatchKind.JOURNEY:
            if not self.journey_id or self.opportunity_save_id:
                errors["journey"] = "Un watch Journey exige uniquement une Journey."
            elif self.journey.beneficiary_id != self.recipient_id:
                errors["recipient"] = "Le recipient doit être le bénéficiaire Profile de la Journey."
        else:
            errors["watch_kind"] = "Type de watch Proactive Preparation inconnu."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
