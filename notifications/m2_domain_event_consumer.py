from django.urls import reverse

from domain_events.contracts import DomainEventType
from domain_events.registry import register_consumer
from journeys.models import Journey
from preparation.models import ActivityResource, ResourceStatus
from questionnaires.models import FormRequest, FormResponse

from .models import NotificationCategory, NotificationKind
from .services import create_notification


CONSUMER_NAME = "notifications.m2_preparation"
EVENT_TYPES = {
    DomainEventType.FORM_REQUESTED,
    DomainEventType.FORM_REOPENED,
    DomainEventType.RESOURCE_PUBLISHED,
    DomainEventType.RESOURCE_REPLACED,
}


def _notify_form(event):
    request_id = event.payload.get("form_request_id")
    form_request = (
        FormRequest.objects.select_related(
            "journey__beneficiary",
            "journey__activity",
            "target_profile",
            "form_version",
            "form_version__form__activity",
        )
        .filter(pk=request_id)
        .first()
    )
    recipient = form_request.recipient if form_request else None
    if not form_request or recipient is None:
        return
    reopened = event.event_type == DomainEventType.FORM_REOPENED
    metadata = {"form_request_id": str(form_request.pk)}
    if form_request.journey_id:
        metadata["journey_id"] = str(form_request.journey_id)
    if form_request.target_profile_id:
        metadata["target_profile_id"] = str(form_request.target_profile_id)
    create_notification(
        recipient=recipient,
        kind=NotificationKind.SYSTEM,
        category=NotificationCategory.SYSTEM,
        title="Formulaire réouvert" if reopened else "Formulaire à compléter",
        message=(
            f"Le formulaire « {form_request.form_version.title} » a été réouvert pour correction."
            if reopened
            else f"Vous avez un formulaire de préparation à compléter : « {form_request.form_version.title} »."
        ),
        action_url=reverse("questionnaires:request-detail", kwargs={"pk": form_request.pk}),
        dedup_key=f"m2:{event.pk}:{recipient.pk}",
        metadata=metadata,
        domain_event=event,
        activity=form_request.activity,
        journey=form_request.journey if form_request.journey_id else None,
        template_key="form.reopened" if reopened else "form.requested",
    )


def _notify_resource(event):
    if not event.payload.get("significant_update"):
        return
    resource = (
        ActivityResource.objects.select_related("activity", "occurrence")
        .filter(pk=event.payload.get("resource_id"), status=ResourceStatus.PUBLISHED)
        .first()
    )
    if not resource:
        return
    journeys = Journey.objects.filter(activity=resource.activity).exclude(status__in=["rejected", "cancelled", "expired"])
    if resource.occurrence_id:
        journeys = journeys.filter(occurrence_id=resource.occurrence_id)
    journeys = journeys.select_related("beneficiary").exclude(beneficiary=None)
    seen = set()
    for journey in journeys:
        recipient = journey.beneficiary
        if recipient.pk in seen:
            continue
        seen.add(recipient.pk)
        create_notification(
            recipient=recipient,
            kind=NotificationKind.SYSTEM,
            category=NotificationCategory.SYSTEM,
            title="Nouvelle information de préparation",
            message=f"Une ressource importante a été publiée pour « {resource.activity.title} ».",
            action_url=reverse("core:participant-journey-detail", kwargs={"pk": journey.pk}),
            dedup_key=f"m2:{event.pk}:{recipient.pk}",
            metadata={"resource_id": str(resource.pk), "activity_id": str(resource.activity_id)},
            domain_event=event,
            activity=resource.activity,
            journey=journey,
            template_key="resource.replaced" if event.event_type == DomainEventType.RESOURCE_REPLACED else "resource.published",
        )


def consume_m2_preparation_event(event):
    if event.event_type in {DomainEventType.FORM_REQUESTED, DomainEventType.FORM_REOPENED}:
        _notify_form(event)
    else:
        _notify_resource(event)


register_consumer(CONSUMER_NAME, consume_m2_preparation_event, event_types=EVENT_TYPES)
