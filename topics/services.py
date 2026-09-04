from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from .models import OpenToKind, ProfileInterest, ProfileOpenTo, Topic


@transaction.atomic
def replace_profile_interests(*, profile, topic_ids):
    if not getattr(profile, "is_authenticated", False):
        raise PermissionDenied("Connectez-vous pour modifier vos centres d’intérêt.")
    normalized_ids = {str(topic_id) for topic_id in topic_ids}
    topics = list(Topic.objects.filter(pk__in=normalized_ids, is_active=True))
    if len(topics) != len(normalized_ids):
        raise ValidationError({"topics": "Un ou plusieurs centres d’intérêt sont indisponibles."})
    interests = ProfileInterest.objects.select_for_update().filter(profile=profile)
    retained_topic_ids = [topic.pk for topic in topics]
    interests.exclude(topic_id__in=retained_topic_ids).delete()
    existing_topic_ids = set(interests.values_list("topic_id", flat=True))
    ProfileInterest.objects.bulk_create([
        ProfileInterest(profile=profile, topic=topic, is_public=False)
        for topic in topics if topic.pk not in existing_topic_ids
    ])
    return ProfileInterest.objects.filter(profile=profile).select_related("topic").order_by("topic__label", "topic__code")


def set_profile_interest_visibility(*, profile, public_topic_ids):
    if not getattr(profile, "is_authenticated", False):
        raise PermissionDenied("Connectez-vous pour modifier la visibilité de vos centres d’intérêt.")
    ids = {str(value) for value in public_topic_ids}
    interests = ProfileInterest.objects.filter(profile=profile)
    owned = {str(value) for value in interests.values_list("topic_id", flat=True)}
    if not ids.issubset(owned):
        raise ValidationError({"public_topics": "Seuls vos centres d’intérêt peuvent être rendus publics."})
    interests.update(is_public=False)
    interests.filter(topic_id__in=ids).update(is_public=True)


def public_profile_interests(*, profile):
    return ProfileInterest.objects.filter(profile=profile, is_public=True, topic__is_active=True).select_related("topic").order_by("topic__label", "topic__code")


@transaction.atomic
def replace_profile_open_to(*, profile, kinds, public_kinds=(), searchable_kinds=()):
    """Replace explicit Open To declarations for one Profile only.

    No history, follows, interests or other behavioral signal is converted into a
    declaration. New rows are conservative unless visibility is explicitly sent.
    """
    if not getattr(profile, "is_authenticated", False):
        raise PermissionDenied("Connectez-vous pour modifier vos préférences « Ouvert à ».")
    valid = {value for value, _label in OpenToKind.choices}
    kinds, public_kinds, searchable_kinds = set(kinds), set(public_kinds), set(searchable_kinds)
    if not kinds.issubset(valid) or not public_kinds.issubset(kinds) or not searchable_kinds.issubset(kinds):
        raise ValidationError({"open_to": "Une préférence « Ouvert à » est invalide."})
    rows = ProfileOpenTo.objects.select_for_update().filter(profile=profile, topic__isnull=True)
    rows.exclude(kind__in=kinds).delete()
    existing = {row.kind: row for row in rows}
    for kind in kinds:
        row = existing.get(kind)
        if row is None:
            row = ProfileOpenTo(profile=profile, kind=kind)
        row.is_active = True
        row.is_public = kind in public_kinds
        row.is_searchable = kind in searchable_kinds
        row.save()
    return ProfileOpenTo.objects.filter(profile=profile, is_active=True, topic__isnull=True).order_by("kind")


def public_profile_open_to(*, profile):
    return ProfileOpenTo.objects.filter(profile=profile, is_active=True, is_public=True).select_related("topic").order_by("kind", "topic__label")
