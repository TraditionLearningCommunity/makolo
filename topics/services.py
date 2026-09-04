from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from .models import ProfileInterest, Topic


@transaction.atomic
def replace_profile_interests(*, profile, topic_ids):
    """Replace only the authenticated Profile's explicit interest declarations.

    Existing visibility flags are preserved for retained interests. Newly added
    interests are private by default. No behavioral or inferred signal calls this
    service implicitly.
    """
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

    ProfileInterest.objects.bulk_create(
        [
            ProfileInterest(profile=profile, topic=topic, is_public=False)
            for topic in topics
            if topic.pk not in existing_topic_ids
        ]
    )
    return ProfileInterest.objects.filter(profile=profile).select_related("topic").order_by(
        "topic__label", "topic__code"
    )


def public_profile_interests(*, profile):
    """Privacy-safe selector intended for future public-profile consumers (G3+)."""
    return ProfileInterest.objects.filter(
        profile=profile,
        is_public=True,
        topic__is_active=True,
    ).select_related("topic").order_by("topic__label", "topic__code")
