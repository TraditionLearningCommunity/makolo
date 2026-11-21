"""Profile-owned presentation facts shared by Objectives workspaces.

Neither a Project Mandate nor a Dossier Assignment can make another
Profile's Passport or avatar public. This is a read-only projection helper;
authorization to act remains with the owner services.
"""
from django.urls import reverse

from accounts.models import UserProfile
from accounts.profile_visibility import ProfileVisibilityResolver


def profile_public_presentation(profile, *, actor):
    """Return only self/public navigation and owner-visible avatar facts."""
    is_self = actor.pk == profile.pk
    is_public = bool(getattr(profile, "is_active", False)) and (
        UserProfile.objects.filter(
            user_id=profile.pk, public_profile=True,
        ).exists()
    )
    profile_url = (
        reverse("sharing:passport-me") if is_self
        else reverse("sharing:passport-profile", kwargs={"profile_id": profile.pk})
        if is_public else None
    )
    avatar_url = None
    if is_self or (
        is_public and ProfileVisibilityResolver(
            owner=profile, viewer=actor,
        ).field("avatar")
    ):
        image = getattr(profile, "avatar", None)
        if image:
            try:
                avatar_url = image.url
            except ValueError:
                pass
    return {
        "profile_url": profile_url,
        "profile_view": "self" if is_self else "public" if is_public else None,
        "avatar_url": avatar_url,
    }
