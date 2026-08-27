from urllib.parse import urlencode

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from activities.models import Activity, ActivityStatus
from events.models import Event, EventStatus
from notifications.models import NotificationCategory, NotificationKind
from notifications.services import create_notification

from .models import (
    OrganizationFollow,
    OrganizationMembership,
    OrganizationVerificationStatus,
    ProfileFollow,
)


def _notify_event_followers(event_id):
    event = (
        Event.objects.select_related("activity__space")
        .filter(pk=event_id)
        .first()
    )
    if not event or not event.activity.space_id or event.status != EventStatus.PUBLISHED:
        return
    organization = event.activity.space
    if organization.verification_status == OrganizationVerificationStatus.SUSPENDED:
        return
    follows = OrganizationFollow.objects.filter(
        organization=organization,
        notify_new_events=True,
    ).select_related("user")
    for follow in follows.iterator():
        create_notification(
            recipient=follow.user,
            kind=NotificationKind.SYSTEM,
            category=NotificationCategory.MARKETING,
            title=f"Nouvel événement — {organization.name}",
            message=f"{organization.name} vient de publier « {event.title} » sur Makolo.",
            action_url=f"/events/{event.slug}/",
            dedup_key=f"organization-new-event:{event.pk}:{follow.user_id}",
            metadata={"organization_id": str(organization.pk), "event_id": str(event.pk)},
            queue_email=follow.email_new_events,
        )


def _notify_profile_followers(activity_id):
    activity = (
        Activity.objects.select_related("owner_profile", "owner_profile__profile")
        .filter(pk=activity_id)
        .first()
    )
    if not activity or activity.status != ActivityStatus.PUBLISHED or not activity.owner_profile_id:
        return
    owner_profile = activity.owner_profile
    public_profile = getattr(owner_profile, "profile", None)
    if not public_profile or not public_profile.public_profile or not public_profile.searchable:
        return
    follows = ProfileFollow.objects.filter(
        organizer_profile=owner_profile,
        notify_new_activities=True,
    ).select_related("user")
    action_url = f"/discover/?{urlencode({'q': activity.title})}"
    organizer_name = owner_profile.full_name or owner_profile.username
    for follow in follows.iterator():
        create_notification(
            recipient=follow.user,
            kind=NotificationKind.SYSTEM,
            category=NotificationCategory.SYSTEM,
            title=f"Nouvelle activité — {organizer_name}",
            message=f"{organizer_name} vient de publier « {activity.title} » sur Makolo.",
            action_url=action_url,
            dedup_key=f"profile-new-activity:{activity.pk}:{follow.user_id}",
            metadata={
                "organizer_profile_id": str(owner_profile.pk),
                "activity_id": str(activity.pk),
            },
            queue_email=False,
        )


@receiver(post_save, sender=Event, dispatch_uid="organizations.notify_followers_new_event")
def notify_followers_on_published_event(sender, instance, **kwargs):
    if instance.status == EventStatus.PUBLISHED and instance.activity.space_id:
        transaction.on_commit(lambda event_id=instance.pk: _notify_event_followers(event_id))


@receiver(post_save, sender=Activity, dispatch_uid="organizations.notify_profile_followers_new_activity")
def notify_profile_followers_on_published_activity(sender, instance, **kwargs):
    if instance.status == ActivityStatus.PUBLISHED and instance.owner_profile_id:
        transaction.on_commit(lambda activity_id=instance.pk: _notify_profile_followers(activity_id))


@receiver(
    post_save,
    sender=OrganizationMembership,
    dispatch_uid="organizations.sync_legacy_membership_authority",
)
def sync_legacy_membership_authority(sender, instance, raw=False, **kwargs):
    """Compatibility bridge while old callers still write OrganizationMembership.

    It runs in the same transaction as the legacy writer so no request can
    observe a committed compatibility membership without its Team/Mandate
    projection. New code does not rely on this receiver.
    """
    if raw:
        return
    from .services import sync_legacy_membership_to_authority

    sync_legacy_membership_to_authority(instance)
