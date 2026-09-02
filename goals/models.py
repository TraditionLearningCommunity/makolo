import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class PersonalGoalType(models.TextChoices):
    JOURNEYS_COMPLETED = "journeys_completed", "Démarches accomplies"
    ACTIVITIES_COMPLETED = "activities_completed", "Activities accomplies"


class PersonalGoalStatus(models.TextChoices):
    ACTIVE = "active", "Actif"
    COMPLETED = "completed", "Atteint"
    PAUSED = "paused", "En pause"
    CANCELLED = "cancelled", "Annulé"


class PersonalGoal(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="personal_goals",
    )
    goal_type = models.CharField(max_length=32, choices=PersonalGoalType.choices)
    target_value = models.PositiveIntegerField()
    period_start = models.DateField()
    period_end = models.DateField()
    status = models.CharField(
        max_length=16,
        choices=PersonalGoalStatus.choices,
        default=PersonalGoalStatus.ACTIVE,
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "id"]
        constraints = [
            models.CheckConstraint(condition=Q(target_value__gt=0), name="goals_target_positive"),
            models.CheckConstraint(condition=Q(period_end__gte=models.F("period_start")), name="goals_period_valid"),
        ]
        indexes = [
            models.Index(fields=["profile", "status", "period_end"], name="goals_profile_status_end_idx"),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.target_value is not None and self.target_value <= 0:
            errors["target_value"] = "La cible doit être strictement positive."
        if self.period_start and self.period_end and self.period_end < self.period_start:
            errors["period_end"] = "La période doit se terminer après son début."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        if self.pk and not self._state.adding and not getattr(self, "_allow_status_transition", False):
            previous = PersonalGoal.objects.filter(pk=self.pk).values_list("status", flat=True).first()
            if previous is not None and previous != self.status:
                raise ValidationError({"status": "Utilisez les services Goals pour changer cet état."})
        result = super().save(*args, **kwargs)
        self._allow_status_transition = False
        return result

    def __str__(self):
        return f"{self.get_goal_type_display()} — {self.target_value}"
