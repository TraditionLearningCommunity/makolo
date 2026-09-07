from django.contrib.auth import get_user_model

from activities.participant_selectors import occurrence_participant_ids


User = get_user_model()


def occurrence_recipient_ids(occurrence):
    """Compatibility name for Notifications; canonical participation lives with Activity/Occurrence."""

    return occurrence_participant_ids(occurrence)


def occurrence_recipients(occurrence):
    ids = occurrence_recipient_ids(occurrence)
    return User.objects.filter(pk__in=ids, is_active=True).order_by("pk")
