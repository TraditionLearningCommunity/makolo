from __future__ import annotations

import json
from dataclasses import dataclass

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from activities.models import ActivityStatus, OccurrenceStatus
from domain_events.contracts import DomainEventType
from opportunities.models import OpportunityPublicationStatus
from preparation.models import ActivityResource, ResourceStatus, ResourceVisibility
from questionnaires.models import Form, FormVersionStatus
from services.models import ServicePlanTemplate, ServicePlanTemplateStatus
from services.reuse_services import create_reused_service_journey

from .analytics import emit_share_event
from .models import JourneyShareAcceptance, JourneyShareSubject, ShareDelivery, ShareIntent, ShareSubjectType
from .services import (
    DIRECT_DUPLICATE_WINDOW,
    ShareUnavailable,
    _create_delivery,
    _create_envelope,
    _recent_duplicate_delivery,
    _validate_direct_participants,
)


SNAPSHOT_SCHEMA_VERSION = 1
MAX_SNAPSHOT_BYTES = 64 * 1024
MAX_STEPS = 200
MAX_FORMS = 50
MAX_RESOURCES = 100
REUSABLE = "REUSABLE"
PERSONALIZE = "PERSONALIZE"
REVALIDATE = "REVALIDATE"
EXCLUDED = "EXCLUDED"

EXCLUDED_POLICY = [
    "form_answers", "private_notes", "personal_documents", "identity_documents",
    "payments_and_receipts", "access_and_credentials", "assignments", "personal_blockers",
    "approvals_and_decisions", "eligibility_results",
]


@dataclass(frozen=True)
class CreatedJourneyShare:
    envelope: object
    delivery: ShareDelivery
    subject: JourneyShareSubject


@dataclass(frozen=True)
class AcceptedJourneyShare:
    delivery: ShareDelivery
    acceptance: JourneyShareAcceptance
    journey: object


def _step_classification(kind):
    if kind == "document":
        return PERSONALIZE
    if kind in {"payment", "review", "submission", "decision", "meeting"}:
        return REVALIDATE
    return REUSABLE


def _require_shareable_source(journey, actor):
    if not getattr(actor, "is_authenticated", False) or not actor.is_active:
        raise PermissionDenied("Authentification requise.")
    if journey.beneficiary_id != actor.pk or journey.initiated_by_id != actor.pk:
        raise PermissionDenied("Seule votre propre Journey personnelle peut être transformée en parcours réutilisable.")
    if journey.external_beneficiary_id:
        raise ValidationError("Les Journeys d’un bénéficiaire externe ne sont pas partageables dans P3.")
    if journey.workflow != "service":
        raise ValidationError("Cette première version de la reprise est limitée aux Journeys Services structurées.")
    try:
        context = journey.service_context
    except Exception as exc:
        raise ValidationError("Cette Journey ne possède pas de structure Services réutilisable.") from exc
    template = context.service_plan_template
    if template is None or template.status not in {ServicePlanTemplateStatus.PUBLISHED, ServicePlanTemplateStatus.RETIRED}:
        raise ValidationError("Cette Journey ne possède pas de plan canonique réutilisable.")
    if not template.steps.exists():
        raise ValidationError("Ce parcours ne contient actuellement aucun élément réutilisable.")
    return context, template


def _snapshot_counts(elements):
    counts = {REUSABLE: 0, PERSONALIZE: 0, REVALIDATE: 0, EXCLUDED: 0}
    for item in elements:
        classification = item.get("classification")
        if classification in counts:
            counts[classification] += 1
    return counts


def build_journey_share_snapshot(*, journey, actor):
    context, template = _require_shareable_source(journey, actor)
    template_steps = list(template.steps.all().prefetch_related("dependencies").order_by("position", "created_at", "id"))
    if len(template_steps) > MAX_STEPS:
        raise ValidationError("Ce parcours contient trop d’étapes pour être partagé en une seule fois.")
    step_refs = {step.pk: f"step-{index + 1}" for index, step in enumerate(template_steps)}
    steps = [{
        "ref": step_refs[step.pk], "template_step_id": str(step.pk), "kind": step.kind,
        "title": step.title, "description": step.description, "position": step.position,
        "is_required": step.is_required, "classification": _step_classification(step.kind),
        "depends_on": [step_refs[d.depends_on_id] for d in step.dependencies.all() if d.depends_on_id in step_refs],
    } for step in template_steps]
    form_requests = list(journey.form_requests.select_related("form_version", "form_version__form").order_by("created_at", "id")[: MAX_FORMS + 1])
    if len(form_requests) > MAX_FORMS:
        raise ValidationError("Ce parcours référence trop de formulaires pour être partagé.")
    forms = [{
        "form_id": str(request.form_version.form_id), "source_form_version_id": str(request.form_version_id),
        "source_version": request.form_version.version, "required": request.required, "classification": PERSONALIZE,
    } for request in form_requests]
    resource_filter = Q(occurrence__isnull=True)
    if journey.occurrence_id:
        resource_filter |= Q(occurrence_id=journey.occurrence_id)
    resources = list(ActivityResource.objects.filter(
        resource_filter, activity_id=journey.activity_id, status=ResourceStatus.PUBLISHED,
        visibility=ResourceVisibility.PUBLIC,
    ).order_by("key", "-version")[: MAX_RESOURCES + 1])
    if len(resources) > MAX_RESOURCES:
        raise ValidationError("Ce parcours référence trop de ressources publiques pour être partagé.")
    resource_items = [{
        "resource_id": str(resource.pk), "key": resource.key, "source_version": resource.version,
        "kind": resource.kind, "occurrence_id": str(resource.occurrence_id) if resource.occurrence_id else None,
        "classification": REUSABLE,
    } for resource in resources]
    opportunity = None
    if context.opportunity_id and context.opportunity_revision_id:
        opportunity = {
            "opportunity_id": str(context.opportunity_id), "source_revision_id": str(context.opportunity_revision_id),
            "source_version": context.opportunity_revision.version, "classification": REVALIDATE,
        }
    all_items = [*steps, *forms, *resource_items]
    if opportunity:
        all_items.append(opportunity)
    snapshot = {
        "schema_version": SNAPSHOT_SCHEMA_VERSION, "workflow": journey.workflow,
        "activity_id": str(journey.activity_id), "occurrence_id": str(journey.occurrence_id) if journey.occurrence_id else None,
        "service_template": {"template_id": str(template.pk), "key": template.key, "source_version": template.version},
        "steps": steps, "forms": forms, "resources": resource_items, "opportunity": opportunity,
        "counts": _snapshot_counts(all_items), "excluded_policy": EXCLUDED_POLICY,
    }
    encoded = json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if len(encoded) > MAX_SNAPSHOT_BYTES:
        raise ValidationError("Le snapshot de ce parcours dépasse la taille maximale autorisée.")
    return snapshot


@transaction.atomic
def create_direct_journey_share(*, created_by, recipient, journey, expires_at=None):
    _validate_direct_participants(created_by=created_by, recipient=recipient)
    _require_shareable_source(journey, created_by)
    duplicate = _recent_duplicate_delivery(
        created_by=created_by, recipient=recipient, subject_type=ShareSubjectType.JOURNEY,
        intent=ShareIntent.START_JOURNEY, journey_id=journey.pk,
    )
    if duplicate:
        return CreatedJourneyShare(envelope=duplicate.envelope, delivery=duplicate, subject=duplicate.envelope.journey_subject)
    snapshot = build_journey_share_snapshot(journey=journey, actor=created_by)
    envelope = _create_envelope(created_by=created_by, subject_type=ShareSubjectType.JOURNEY, intent=ShareIntent.START_JOURNEY, expires_at=expires_at)
    subject = JourneyShareSubject.objects.create(envelope=envelope, source_journey=journey, snapshot=snapshot)
    emit_share_event(event_type=DomainEventType.SHARE_CREATED, envelope=envelope, idempotency_suffix="created", channel="journey_reuse")
    delivery = _create_delivery(envelope=envelope, recipient=recipient)
    return CreatedJourneyShare(envelope=envelope, delivery=delivery, subject=subject)


def resolve_journey_share_subject(envelope):
    if envelope.subject_type != ShareSubjectType.JOURNEY:
        raise ShareUnavailable
    try:
        subject = envelope.journey_subject
    except JourneyShareSubject.DoesNotExist as exc:
        raise ShareUnavailable from exc
    if subject.source_journey_id is None or subject.snapshot.get("schema_version") != SNAPSHOT_SCHEMA_VERSION:
        raise ShareUnavailable
    return subject, subject.source_journey


def _current_template(subject, source_journey):
    snapshot_template = subject.snapshot.get("service_template") or {}
    key = snapshot_template.get("key")
    if not key:
        raise ShareUnavailable
    try:
        service = source_journey.activity.service_details
    except Exception as exc:
        raise ShareUnavailable from exc
    template = ServicePlanTemplate.objects.filter(service=service, key=key, status=ServicePlanTemplateStatus.PUBLISHED).order_by("-version", "-created_at").first()
    if template is None:
        raise ShareUnavailable
    return template


def evaluate_journey_share(subject):
    source_journey = subject.source_journey
    if source_journey is None or source_journey.activity.status != ActivityStatus.PUBLISHED:
        raise ShareUnavailable
    if source_journey.occurrence_id:
        occurrence = source_journey.occurrence
        if occurrence.status != OccurrenceStatus.SCHEDULED or (occurrence.end_at or occurrence.start_at) <= timezone.now():
            raise ShareUnavailable
    current_template = _current_template(subject, source_journey)
    stale = []
    source_template = subject.snapshot.get("service_template") or {}
    if str(current_template.pk) != source_template.get("template_id"):
        stale.append("service_template")
    opportunity = None
    opportunity_revision = None
    opportunity_snapshot = subject.snapshot.get("opportunity")
    if opportunity_snapshot:
        try:
            opportunity = source_journey.service_context.opportunity
        except Exception as exc:
            raise ShareUnavailable from exc
        if opportunity is None or opportunity.publication_status != OpportunityPublicationStatus.PUBLISHED:
            raise ShareUnavailable
        opportunity_revision = opportunity.current_revision
        if opportunity_revision is None or opportunity_revision.temporal_state() == "closed":
            raise ShareUnavailable
        if str(opportunity_revision.pk) != opportunity_snapshot.get("source_revision_id"):
            stale.append("opportunity_revision")
    form_revalidation = 0
    for form_snapshot in subject.snapshot.get("forms", []):
        form = Form.objects.filter(pk=form_snapshot.get("form_id"), activity_id=source_journey.activity_id).first()
        current_version = form.versions.filter(status=FormVersionStatus.PUBLISHED).order_by("-version", "-created_at").first() if form else None
        if current_version is None or str(current_version.pk) != form_snapshot.get("source_form_version_id"):
            form_revalidation += 1
    resource_revalidation = 0
    for resource_snapshot in subject.snapshot.get("resources", []):
        query = ActivityResource.objects.filter(activity_id=source_journey.activity_id, key=resource_snapshot.get("key"), status=ResourceStatus.PUBLISHED, visibility=ResourceVisibility.PUBLIC)
        occurrence_id = resource_snapshot.get("occurrence_id")
        query = query.filter(occurrence_id=occurrence_id) if occurrence_id else query.filter(occurrence__isnull=True)
        current_resource = query.order_by("-version", "-created_at").first()
        if current_resource is None or str(current_resource.pk) != resource_snapshot.get("resource_id"):
            resource_revalidation += 1
    counts = dict(subject.snapshot.get("counts") or {})
    counts.setdefault(REUSABLE, 0); counts.setdefault(PERSONALIZE, 0); counts.setdefault(REVALIDATE, 0)
    counts[REVALIDATE] += len(stale) + form_revalidation + resource_revalidation
    return {"counts": counts, "stale": stale, "form_revalidation": form_revalidation, "resource_revalidation": resource_revalidation, "current_template": current_template, "opportunity": opportunity, "opportunity_revision": opportunity_revision}


@transaction.atomic
def accept_journey_share(*, delivery_id, user):
    if not getattr(user, "is_authenticated", False) or not user.is_active:
        raise PermissionDenied("Authentification requise.")
    try:
        profile = user.profile
    except Exception as exc:
        raise PermissionDenied("Profil indisponible.") from exc
    delivery = ShareDelivery.objects.select_for_update(of=("self",)).select_related("envelope", "recipient", "recipient__user").get(pk=delivery_id)
    envelope = ShareDelivery.objects.select_related("envelope").get(pk=delivery.pk).envelope
    envelope = type(envelope).objects.select_for_update(of=("self",)).get(pk=envelope.pk)
    delivery.envelope = envelope
    if delivery.recipient_id != profile.pk:
        raise PermissionDenied("Ce partage n’est pas disponible pour ce compte.")
    if not envelope.is_active_at():
        raise ShareUnavailable
    if delivery.declined_at:
        raise ValidationError("Ce partage a déjà été ignoré.")
    existing = JourneyShareAcceptance.objects.select_related("resulting_journey").filter(delivery=delivery).first()
    if existing is not None:
        return AcceptedJourneyShare(delivery=delivery, acceptance=existing, journey=existing.resulting_journey)
    subject = JourneyShareSubject.objects.select_related("source_journey", "source_journey__activity", "source_journey__occurrence", "source_journey__activity__service_details").get(envelope=envelope)
    evaluation = evaluate_journey_share(subject)
    journey = create_reused_service_journey(
        source_journey=subject.source_journey, recipient=user, template=evaluation["current_template"],
        opportunity=evaluation["opportunity"], opportunity_revision=evaluation["opportunity_revision"],
    )
    acceptance = JourneyShareAcceptance.objects.create(delivery=delivery, resulting_journey=journey)
    delivery.accepted_at = acceptance.accepted_at
    delivery.save(update_fields=["accepted_at"])
    emit_share_event(event_type=DomainEventType.SHARE_ACCEPTED, envelope=envelope, idempotency_suffix=f"accepted:{delivery.pk}", recipient_id=profile.pk, resulting_journey_id=journey.pk)
    emit_share_event(event_type=DomainEventType.JOURNEY_STARTED_FROM_SHARE, envelope=envelope, idempotency_suffix=f"journey-started:{journey.pk}", recipient_id=profile.pk, resulting_journey_id=journey.pk, channel="journey_reuse")
    return AcceptedJourneyShare(delivery=delivery, acceptance=acceptance, journey=journey)
