"""Selection commune des beneficiaires de demonstration.

Un username explicite prend la priorite. Sans username, le comportement
historique conserve les profils synthetiques world_*.
"""
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError


def demo_profiles(*, username=None, limit=30):
    candidates = get_user_model().objects.filter(
        is_active=True, is_staff=False, is_superuser=False)
    if username:
        candidates = candidates.filter(username=username)
    else:
        candidates = candidates.filter(username__startswith="world_")
    users = list(candidates.order_by("username")[:limit])
    if not users:
        raise ValidationError("Aucun profil eligible pour cette selection.")
    return users
