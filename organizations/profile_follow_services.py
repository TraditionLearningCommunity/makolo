from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from .models import ProfileFollow


@transaction.atomic
def follow_profile(*, user, organizer_profile) -> ProfileFollow:
    if not getattr(user, "is_authenticated", False):
        raise PermissionDenied("Connectez-vous pour suivre un organisateur.")
    if organizer_profile.pk == user.pk:
        raise ValidationError("Vous ne pouvez pas suivre votre propre Profil.")
    profile = getattr(organizer_profile, "profile", None)
    if not profile or not profile.public_profile or not profile.searchable:
        raise ValidationError("Ce Profil organisateur ne peut pas être suivi actuellement.")
    follow, _ = ProfileFollow.objects.get_or_create(
        organizer_profile=organizer_profile,
        user=user,
    )
    return follow


@transaction.atomic
def unfollow_profile(*, follow: ProfileFollow, user) -> None:
    follow = ProfileFollow.objects.select_for_update().get(pk=follow.pk)
    if follow.user_id != getattr(user, "pk", None):
        raise PermissionDenied("Vous ne pouvez supprimer que vos propres abonnements.")
    follow.delete()
