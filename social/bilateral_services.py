from __future__ import annotations

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone

from authorization.constants import PermissionCode
from authorization.services import can
from notifications.models import NotificationCategory, NotificationKind
from notifications.services import create_notification

from .models import ActionNeed, ActionNeedStatus, ProfileSolicitation, ProfileSolicitationStatus
from .profile_search import profile_is_eligible_for_need


def _authenticated(actor) -> bool:
    return bool(actor and getattr(actor, "is_authenticated", False))


def can_manage_action_need(actor, need: ActionNeed) -> bool:
    """Resolve authority from personal ownership or canonical Mandates."""

    if not _authenticated(actor):
        return False
    if getattr(actor, "is_superuser", False):
        return True
    if need.owner_profile_id:
        if need.owner_profile_id != actor.pk:
            return False
        if need.activity_id:
            return need.activity.owner_profile_id == actor.pk
        return True
    if not need.space_id:
        return False
    if need.activity_id:
        return need.activity.space_id == need.space_id and can(
            actor, PermissionCode.ACTIVITY_MANAGE, activity=need.activity
        )
    return can(actor, PermissionCode.SPACE_MANAGE, space=need.space)


def _require_need_authority(*, actor, owner_profile=None, space=None, activity=None) -> None:
    if not _authenticated(actor):
        raise PermissionDenied("Connectez-vous pour gérer un besoin.")
    if bool(owner_profile) == bool(space):
        raise ValidationError("Un besoin appartient soit à un Profile, soit à un Space.")
    if owner_profile is not None:
        if owner_profile.pk != actor.pk:
            raise PermissionDenied("Vous ne pouvez créer qu'un besoin personnel pour votre propre Profile.")
        if activity is not None and activity.owner_profile_id != actor.pk:
            raise PermissionDenied("Cette Activity n'appartient pas à votre contexte personnel.")
        return
    if activity is not None:
        if activity.space_id != space.pk:
            raise ValidationError({"activity": "L'Activity doit appartenir au Space du besoin."})
        if not can(actor, PermissionCode.ACTIVITY_MANAGE, activity=activity):
            raise PermissionDenied("Cette Activity exige l'autorité ACTIVITY_MANAGE.")
        return
    if not can(actor, PermissionCode.SPACE_MANAGE, space=space):
        raise PermissionDenied("Ce besoin Space exige l'autorité SPACE_MANAGE.")


@transaction.atomic
def create_action_need(
    *, actor, title, open_to_kind, description="", owner_profile=None, space=None,
    topics=(), activity=None, opportunity=None,
) -> ActionNeed:
    _require_need_authority(actor=actor, owner_profile=owner_profile, space=space, activity=activity)
    need = ActionNeed(
        owner_profile=owner_profile,
        space=space,
        created_by=actor,
        title=title,
        description=description,
        open_to_kind=open_to_kind,
        activity=activity,
        opportunity=opportunity,
    )
    need.full_clean()
    need.save()
    if topics:
        need.topics.set(topics)
    return need


@transaction.atomic
def close_action_need(*, actor, need: ActionNeed) -> ActionNeed:
    locked = ActionNeed.objects.select_for_update().select_related(
        "owner_profile", "space", "activity"
    ).get(pk=need.pk)
    if not can_manage_action_need(actor, locked):
        raise PermissionDenied("Vous ne pouvez pas fermer ce besoin.")
    if locked.status == ActionNeedStatus.CLOSED:
        return locked
    locked.status = ActionNeedStatus.CLOSED
    locked._allow_status_transition = True
    locked.save(update_fields=["status", "updated_at"])
    return locked


@transaction.atomic
def create_profile_solicitation(*, actor, need: ActionNeed, recipient_profile, message="") -> ProfileSolicitation:
    locked_need = ActionNeed.objects.select_for_update().select_related(
        "owner_profile", "space", "activity", "created_by"
    ).get(pk=need.pk)
    if locked_need.status != ActionNeedStatus.OPEN:
        raise ValidationError("Une nouvelle sollicitation exige un besoin ouvert.")
    if not can_manage_action_need(actor, locked_need):
        raise PermissionDenied("Vous ne pouvez pas solliciter des Profiles pour ce besoin.")
    if locked_need.owner_profile_id and locked_need.owner_profile_id == recipient_profile.pk:
        raise ValidationError("Vous ne pouvez pas vous solliciter vous-même pour un besoin personnel.")
    if not profile_is_eligible_for_need(need=locked_need, profile=recipient_profile):
        raise ValidationError("Ce Profile n'est pas découvrable pour ce besoin selon ses réglages actuels.")
    if ProfileSolicitation.objects.filter(
        need=locked_need,
        recipient_profile=recipient_profile,
        status=ProfileSolicitationStatus.PENDING,
    ).exists():
        raise ValidationError("Une sollicitation identique est déjà en attente pour ce Profile.")
    try:
        solicitation = ProfileSolicitation.objects.create(
            need=locked_need,
            recipient_profile=recipient_profile,
            sent_by=actor,
            message=(message or "").strip(),
        )
    except IntegrityError as exc:
        raise ValidationError("Une sollicitation identique est déjà en attente pour ce Profile.") from exc

    create_notification(
        recipient=recipient_profile,
        kind=NotificationKind.SYSTEM,
        category=NotificationCategory.SYSTEM,
        title="Nouvelle sollicitation Makolo",
        message=f"{locked_need.owner_display_name} vous sollicite pour « {locked_need.title} ».",
        action_url=reverse("social:my-solicitations"),
        dedup_key=f"g7-solicitation:{solicitation.pk}",
        metadata={"solicitation_id": str(solicitation.pk), "need_id": str(locked_need.pk)},
        queue_email=False,
    )
    return solicitation


@transaction.atomic
def respond_to_profile_solicitation(*, actor, solicitation: ProfileSolicitation, status: str) -> ProfileSolicitation:
    if status not in {ProfileSolicitationStatus.ACCEPTED, ProfileSolicitationStatus.DECLINED}:
        raise ValidationError({"status": "Réponse de sollicitation invalide."})
    locked = ProfileSolicitation.objects.select_for_update().select_related(
        "recipient_profile", "sent_by", "need", "need__space", "need__owner_profile"
    ).get(pk=solicitation.pk)
    if locked.recipient_profile_id != getattr(actor, "pk", None):
        raise PermissionDenied("Seul le Profile destinataire peut répondre à cette sollicitation.")
    if locked.status != ProfileSolicitationStatus.PENDING:
        raise ValidationError("Cette sollicitation n'est plus en attente.")

    locked.status = status
    locked.responded_at = timezone.now()
    locked._allow_status_transition = True
    locked.save(update_fields=["status", "responded_at", "updated_at"])

    verb = "accepté" if status == ProfileSolicitationStatus.ACCEPTED else "refusé"
    display_name = actor.full_name or actor.username
    create_notification(
        recipient=locked.sent_by,
        kind=NotificationKind.SYSTEM,
        category=NotificationCategory.SYSTEM,
        title="Réponse à une sollicitation Makolo",
        message=f"{display_name} a {verb} la sollicitation « {locked.need.title} ».",
        action_url=reverse("social:need-detail", kwargs={"pk": locked.need_id}),
        dedup_key=f"g7-solicitation-response:{locked.pk}:{status}",
        metadata={"solicitation_id": str(locked.pk), "need_id": str(locked.need_id), "status": status},
        queue_email=False,
    )
    return locked


@transaction.atomic
def cancel_profile_solicitation(*, actor, solicitation: ProfileSolicitation) -> ProfileSolicitation:
    locked = ProfileSolicitation.objects.select_for_update().get(pk=solicitation.pk)
    if locked.sent_by_id != getattr(actor, "pk", None):
        raise PermissionDenied("Seul l'expéditeur peut annuler cette sollicitation.")
    if locked.status != ProfileSolicitationStatus.PENDING:
        raise ValidationError("Seule une sollicitation en attente peut être annulée.")
    locked.status = ProfileSolicitationStatus.CANCELLED
    locked.cancelled_at = timezone.now()
    locked._allow_status_transition = True
    locked.save(update_fields=["status", "cancelled_at", "updated_at"])
    return locked
