from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from questionnaires.models import FormRequestStatus, FormVersionStatus
from questionnaires.services import request_form_for_profile

from .audience_services import resolve_audience_ids
from .core_models import ConversationContextKind
from .form_models import ConversationPointFormRequest
from .point_models import ConversationPoint, ConversationPointKind
from .services import can_publish_in_conversation


User = get_user_model()


def _conversation_activity(conversation):
    context = conversation.context
    if context.kind == ConversationContextKind.ACTIVITY:
        return context.activity
    if context.kind == ConversationContextKind.OCCURRENCE:
        return context.occurrence.activity
    if context.kind == ConversationContextKind.JOURNEY:
        return context.journey.activity
    if context.kind == ConversationContextKind.ACTION_PROPOSAL and context.action_proposal.need.activity_id:
        return context.action_proposal.need.activity
    return None


def _point_form_audience(point):
    return point.expected_action_audience or point.response_audience or point.visibility_audience


@transaction.atomic
def ensure_form_requests_for_point(*, actor, point: ConversationPoint, form_version):
    """Materialize one canonical FormRequest per currently expected Profile.

    Audience remains derived. Only questionnaire obligations are materialized because
    each respondent needs an independent canonical response lifecycle.
    """

    locked = ConversationPoint.objects.select_for_update(of=("self",)).select_related("conversation__context").get(pk=point.pk)
    if locked.kind != ConversationPointKind.FORM_REQUEST:
        raise ValidationError("Ce Point n’est pas un Point Formulaire.")
    if not can_publish_in_conversation(actor, locked.conversation):
        raise PermissionDenied("Vous ne pouvez pas publier ce formulaire dans cette Conversation.")
    if form_version.status != FormVersionStatus.PUBLISHED:
        raise ValidationError("Seule une version publiée peut être demandée.")
    activity = _conversation_activity(locked.conversation)
    if activity is None or activity.pk != form_version.form.activity_id:
        raise ValidationError("Le Form doit appartenir à l’Activity canonique de cette Conversation.")
    audience = _point_form_audience(locked)
    if audience is None:
        raise ValidationError("Un Point Formulaire doit définir une audience attendue.")

    target_ids = resolve_audience_ids(audience)
    existing = {
        link.target_profile_id: link
        for link in ConversationPointFormRequest.objects.select_related("form_request").filter(
            point=locked,
            target_profile_id__in=target_ids,
        )
    }
    created = []
    for profile in User.objects.filter(pk__in=target_ids, is_active=True).order_by("pk"):
        if profile.pk in existing:
            created.append(existing[profile.pk])
            continue
        form_request = request_form_for_profile(
            form_version=form_version,
            profile=profile,
            actor=actor,
            required=True,
            opens_at=locked.opens_at,
            due_at=locked.deadline_at,
        )
        created.append(
            ConversationPointFormRequest.objects.create(
                point=locked,
                target_profile=profile,
                form_request=form_request,
            )
        )
    return created


def form_request_for_profile(point, profile):
    if not getattr(profile, "is_authenticated", False):
        return None
    link = (
        ConversationPointFormRequest.objects.select_related("form_request")
        .filter(point=point, target_profile=profile)
        .first()
    )
    return link.form_request if link else None


def form_request_completed_for_profile(point, profile):
    form_request = form_request_for_profile(point, profile)
    return bool(form_request and form_request.status == FormRequestStatus.COMPLETED)
