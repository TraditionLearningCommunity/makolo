from __future__ import annotations

from django.contrib.auth import get_user_model

from authorization.constants import PermissionCode
from authorization.models import AuthorityScope, Mandate, MandateStatus
from authorization.services import can
from domain_events.contracts import DomainEventType
from domain_events.registry import register_consumer
from organizations.models import Organization
from subscriptions.contracts import RequirementDisclosure
from subscriptions.eligibility_models import PlanRequirement

from .models import NotificationCategory, NotificationKind
from .services import create_notification


CONSUMER_NAME = "notifications.subscriptions"
EVENT_TYPES = {
    DomainEventType.SUBSCRIPTION_TRANSITION_READY,
    DomainEventType.SUBSCRIPTION_TRANSITION_COMPLETED,
    DomainEventType.SUBSCRIPTION_TRANSITION_REJECTED,
    DomainEventType.SUBSCRIPTION_TRANSITION_EXPIRED,
    DomainEventType.SUBSCRIPTION_REQUIREMENT_CHANGED,
    DomainEventType.SUBSCRIPTION_GRACE_STARTED,
    DomainEventType.SUBSCRIPTION_GRACE_ENDED,
    DomainEventType.SUBSCRIPTION_SUSPENDED,
    DomainEventType.SUBSCRIPTION_REACTIVATED,
    DomainEventType.SUBSCRIPTION_ELIGIBILITY_AVAILABLE,
}


def _dedup(event, recipient, template_key):
    return f"domain:{event.pk}:{recipient.pk}:{template_key}"[:255]


def _recipients(event):
    payload = event.payload or {}
    subject_type = payload.get("subject_type")
    subject_id = payload.get("subject_id")
    if not subject_id:
        return []
    User = get_user_model()
    if subject_type == "profile":
        recipient = User.objects.filter(pk=subject_id, is_active=True).first()
        return [recipient] if recipient else []
    if subject_type != "space":
        return []

    space = Organization.objects.filter(pk=subject_id).first()
    if not space:
        return []
    seen = set()
    recipients = []
    mandates = (
        Mandate.objects.filter(
            scope_type=AuthorityScope.SPACE,
            space=space,
            status=MandateStatus.ACTIVE,
            profile__is_active=True,
        )
        .select_related("profile", "role")
        .order_by("profile_id")
    )
    for mandate in mandates:
        profile = mandate.profile
        if profile.pk in seen:
            continue
        seen.add(profile.pk)
        if can(profile, PermissionCode.SPACE_SUBSCRIPTION_VIEW, space=space):
            recipients.append(profile)
    return recipients


def _notify(event, *, template_key, title, message, metadata=None):
    for recipient in _recipients(event):
        create_notification(
            recipient=recipient,
            kind=NotificationKind.SYSTEM,
            category=NotificationCategory.SYSTEM,
            title=title,
            message=message,
            dedup_key=_dedup(event, recipient, template_key),
            metadata=metadata or {},
            domain_event=event,
            template_key=template_key,
        )


def _notify_transition(event):
    messages = {
        DomainEventType.SUBSCRIPTION_TRANSITION_READY: (
            "subscription.transition.ready",
            "Changement d’abonnement prêt",
            "Les conditions requises sont satisfaites et le changement d’abonnement est prêt.",
        ),
        DomainEventType.SUBSCRIPTION_TRANSITION_COMPLETED: (
            "subscription.transition.completed",
            "Abonnement mis à jour",
            "Le changement d’abonnement a été appliqué.",
        ),
        DomainEventType.SUBSCRIPTION_TRANSITION_REJECTED: (
            "subscription.transition.rejected",
            "Changement d’abonnement refusé",
            "Le changement d’abonnement n’a pas été accepté.",
        ),
        DomainEventType.SUBSCRIPTION_TRANSITION_EXPIRED: (
            "subscription.transition.expired",
            "Demande d’abonnement expirée",
            "La demande de changement d’abonnement a expiré.",
        ),
    }
    template_key, title, message = messages[event.event_type]
    _notify(event, template_key=template_key, title=title, message=message)


def _notify_requirement(event):
    payload = event.payload or {}
    if payload.get("new_state") != "unsatisfied":
        return
    disclosure = payload.get("disclosure")
    if disclosure == RequirementDisclosure.INTERNAL:
        return
    message = "Une condition nécessaire à votre abonnement n’est plus satisfaite."
    if disclosure == RequirementDisclosure.VISIBLE:
        requirement = PlanRequirement.objects.filter(pk=payload.get("requirement_id")).only("title").first()
        if requirement:
            message = f"Condition à vérifier : {requirement.title}."
    _notify(
        event,
        template_key="subscription.requirement.unsatisfied",
        title="Condition d’abonnement à vérifier",
        message=message,
    )


def _notify_lifecycle(event):
    values = {
        DomainEventType.SUBSCRIPTION_GRACE_STARTED: (
            "subscription.grace.started",
            "Période de grâce de l’abonnement",
            "Une condition n’est plus satisfaite. Votre abonnement reste temporairement actif pendant la période de grâce.",
        ),
        DomainEventType.SUBSCRIPTION_GRACE_ENDED: (
            "subscription.grace.ended",
            "Condition d’abonnement rétablie",
            "Les conditions applicables sont de nouveau satisfaites et la période de grâce est terminée.",
        ),
        DomainEventType.SUBSCRIPTION_SUSPENDED: (
            "subscription.suspended",
            "Abonnement suspendu",
            "L’accès à certaines capacités d’abonnement est suspendu jusqu’au rétablissement des conditions applicables.",
        ),
        DomainEventType.SUBSCRIPTION_REACTIVATED: (
            "subscription.reactivated",
            "Abonnement réactivé",
            "Les conditions applicables sont de nouveau satisfaites et l’abonnement est réactivé.",
        ),
    }
    template_key, title, message = values[event.event_type]
    _notify(event, template_key=template_key, title=title, message=message)


def _notify_eligibility(event):
    _notify(
        event,
        template_key="subscription.eligibility.available",
        title="Une formule est maintenant disponible",
        message="Une formule d’abonnement pertinente est maintenant disponible pour votre profil ou votre Espace.",
        metadata={"plan_version_id": (event.payload or {}).get("plan_version_id")},
    )


def consume_subscription_event(event):
    if event.event_type in {
        DomainEventType.SUBSCRIPTION_TRANSITION_READY,
        DomainEventType.SUBSCRIPTION_TRANSITION_COMPLETED,
        DomainEventType.SUBSCRIPTION_TRANSITION_REJECTED,
        DomainEventType.SUBSCRIPTION_TRANSITION_EXPIRED,
    }:
        _notify_transition(event)
    elif event.event_type == DomainEventType.SUBSCRIPTION_REQUIREMENT_CHANGED:
        _notify_requirement(event)
    elif event.event_type in {
        DomainEventType.SUBSCRIPTION_GRACE_STARTED,
        DomainEventType.SUBSCRIPTION_GRACE_ENDED,
        DomainEventType.SUBSCRIPTION_SUSPENDED,
        DomainEventType.SUBSCRIPTION_REACTIVATED,
    }:
        _notify_lifecycle(event)
    elif event.event_type == DomainEventType.SUBSCRIPTION_ELIGIBILITY_AVAILABLE:
        _notify_eligibility(event)


register_consumer(CONSUMER_NAME, consume_subscription_event, event_types=EVENT_TYPES)
