from __future__ import annotations

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from notifications.models import NotificationCategory, NotificationKind
from notifications.services import create_notification

from .models import PersonalGoal, PersonalGoalStatus, PersonalGoalType
from .selectors import goal_progresses


def _require_owner(actor, goal):
    if not getattr(actor, "is_authenticated", False) or goal.profile_id != getattr(actor, "pk", None):
        raise PermissionDenied("Cet objectif personnel ne vous appartient pas.")


@transaction.atomic
def create_personal_goal(*, profile, goal_type, target_value, period_start, period_end):
    if not getattr(profile, "is_authenticated", False):
        raise PermissionDenied("Connectez-vous pour créer un objectif.")
    if goal_type not in PersonalGoalType.values:
        raise ValidationError({"goal_type": "Type d'objectif inconnu."})
    goal = PersonalGoal(
        profile=profile,
        goal_type=goal_type,
        target_value=target_value,
        period_start=period_start,
        period_end=period_end,
    )
    goal.full_clean()
    goal.save()
    return goal


@transaction.atomic
def set_goal_status(*, actor, goal, status):
    if status not in {PersonalGoalStatus.ACTIVE, PersonalGoalStatus.PAUSED, PersonalGoalStatus.CANCELLED}:
        raise ValidationError({"status": "Transition d'objectif non autorisée."})
    locked = PersonalGoal.objects.select_for_update().get(pk=goal.pk)
    _require_owner(actor, locked)
    if locked.status == PersonalGoalStatus.COMPLETED:
        raise ValidationError("Un objectif atteint reste un fait historique.")
    locked.status = status
    locked.completed_at = None
    locked._allow_status_transition = True
    locked.save(update_fields=["status", "completed_at", "updated_at"])
    return locked


@transaction.atomic
def evaluate_goals(*, profile):
    locked = list(
        PersonalGoal.objects.select_for_update().filter(
            profile=profile,
            status=PersonalGoalStatus.ACTIVE,
        )[:100]
    )
    progresses = goal_progresses(profile, goals=locked)
    completed = []
    now = timezone.now()
    for progress in progresses:
        if not progress.complete:
            continue
        goal = progress.goal
        goal.status = PersonalGoalStatus.COMPLETED
        goal.completed_at = now
        goal._allow_status_transition = True
        goal.save(update_fields=["status", "completed_at", "updated_at"])
        create_notification(
            recipient=profile,
            kind=NotificationKind.SYSTEM,
            category=NotificationCategory.SYSTEM,
            title="Objectif atteint",
            message=f"Votre objectif « {goal.get_goal_type_display()} » est atteint.",
            action_url=reverse("goals:list"),
            dedup_key=f"goal-completed:{goal.pk}",
            metadata={"goal_id": str(goal.pk)},
            queue_email=False,
        )
        completed.append(goal)
    return completed
