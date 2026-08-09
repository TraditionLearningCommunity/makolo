from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from events.models import Event, EventStatus
from notifications.models import NotificationCategory, NotificationKind
from notifications.services import create_notification

from .models import OrganizationFollow, OrganizationVerificationStatus


def _notify_event_followers(event_id):
    event = Event.objects.select_related("organization").filter(pk=event_id).first()
    if not event or not event.organization_id or event.status != EventStatus.PUBLISHED:
        return
    organization = event.organization
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


@receiver(post_save, sender=Event, dispatch_uid="organizations.notify_followers_new_event")
def notify_followers_on_published_event(sender, instance, **kwargs):
    if instance.status == EventStatus.PUBLISHED and instance.organization_id:
        transaction.on_commit(lambda event_id=instance.pk: _notify_event_followers(event_id))
