from __future__ import annotations

from functools import wraps

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from authorization.constants import PermissionCode
from authorization.services import can

from .collaboration_models import (
    JourneyArtifact,
    JourneyArtifactReview,
    JourneyArtifactReviewStatus,
    JourneyArtifactSensitivity,
    JourneyArtifactStatus,
    JourneyAssignment,
    JourneyAssignmentResponsibility,
    JourneyAssignmentStatus,
    JourneyNote,
    JourneyNoteVisibility,
)
from .models import WorkflowKind


CASE_SCOPE_BENEFICIARY = "beneficiary"
CASE_SCOPE_VIEW_ALL = "view_all"
CASE_SCOPE_VIEW_ASSIGNED = "view_assigned"
CASE_SCOPE_NONE = "none"


def _actor_id(actor):
    return getattr(actor, "pk", None) if getattr(actor, "is_authenticated", False) else None


def _is_service(journey):
    return getattr(journey, "workflow", None) == WorkflowKind.SERVICE


def _active_assignment_exists(actor, journey):
    actor_id = _actor_id(actor)
    if not actor_id:
        return False
    return JourneyAssignment.objects.filter(
        journey=journey,
        profile_id=actor_id,
        status=JourneyAssignmentStatus.ACTIVE,
    ).exists()


def service_case_scope(actor, journey):
    """Return the canonical Services case scope without granting any permission."""
    actor_id = _actor_id(actor)
    if not actor_id or not _is_service(journey):
        return CASE_SCOPE_NONE
    if journey.beneficiary_id == actor_id:
        return CASE_SCOPE_BENEFICIARY
    if can(actor, PermissionCode.ACTIVITY_SERVICES_CASES_VIEW_ALL, activity=journey.activity):
        return CASE_SCOPE_VIEW_ALL
    if can(actor, PermissionCode.ACTIVITY_SERVICES_CASES_VIEW_ASSIGNED, activity=journey.activity) and _active_assignment_exists(actor, journey):
        return CASE_SCOPE_VIEW_ASSIGNED
    return CASE_SCOPE_NONE


def _require_operator_scope(actor, journey):
    scope = service_case_scope(actor, journey)
    if scope not in {CASE_SCOPE_VIEW_ALL, CASE_SCOPE_VIEW_ASSIGNED}:
        raise PermissionDenied("Accès refusé à ce dossier Services.")
    return scope


def _require_service_permission(actor, journey, permission_code, *, require_case_manage=False, restricted=False):
    _require_operator_scope(actor, journey)
    if require_case_manage and not can(actor, PermissionCode.ACTIVITY_SERVICES_CASES_MANAGE, activity=journey.activity):
        raise PermissionDenied("La gestion de ce dossier Services n'est pas autorisée.")
    if not can(actor, permission_code, activity=journey.activity):
        raise PermissionDenied("Permission Services insuffisante pour cette action.")
    if restricted and not can(actor, PermissionCode.ACTIVITY_SERVICES_ARTIFACTS_RESTRICTED_VIEW, activity=journey.activity):
        raise PermissionDenied("Ce document Services restreint n'est pas accessible.")


def _target_has_assignment_authority(profile, journey, responsibility):
    can_scope = can(profile, PermissionCode.ACTIVITY_SERVICES_CASES_VIEW_ALL, activity=journey.activity) or can(
        profile,
        PermissionCode.ACTIVITY_SERVICES_CASES_VIEW_ASSIGNED,
        activity=journey.activity,
    )
    if not can_scope:
        return False
    if responsibility == JourneyAssignmentResponsibility.REVIEWER:
        return can(profile, PermissionCode.ACTIVITY_SERVICES_ARTIFACTS_VIEW, activity=journey.activity) and can(
            profile,
            PermissionCode.ACTIVITY_SERVICES_REVIEWS_MANAGE,
            activity=journey.activity,
        )
    return True


def install_service_authorization_policy():
    """Install workflow-aware guards into the generic Journey collaboration services.

    The Journey kernel stays independent from the Services app: this module only knows the
    neutral workflow discriminator plus canonical Authorization permission codes.
    """
    from . import collaboration_services as cs

    if getattr(cs, "_t34b_service_policy_installed", False):
        return

    original_can_access_case = cs.can_access_case
    original_ensure_case_access = cs.ensure_case_access
    original_ensure_case_manager = cs.ensure_case_manager
    original_request_artifact_review = cs.request_artifact_review
    original_ensure_reviewer = cs._ensure_reviewer
    original_notes_for_actor = cs.notes_for_actor
    original_artifacts_for_actor = cs.artifacts_for_actor
    original_artifact_for_download = cs.artifact_for_download

    def can_access_case(actor, journey, *, write=False, restricted=False):
        if not _is_service(journey):
            return original_can_access_case(actor, journey, write=write, restricted=restricted)
        scope = service_case_scope(actor, journey)
        if scope == CASE_SCOPE_BENEFICIARY:
            return not write
        if scope not in {CASE_SCOPE_VIEW_ALL, CASE_SCOPE_VIEW_ASSIGNED}:
            return False
        if write and not can(actor, PermissionCode.ACTIVITY_SERVICES_CASES_MANAGE, activity=journey.activity):
            return False
        if restricted:
            return can(actor, PermissionCode.ACTIVITY_SERVICES_ARTIFACTS_VIEW, activity=journey.activity) and can(
                actor,
                PermissionCode.ACTIVITY_SERVICES_ARTIFACTS_RESTRICTED_VIEW,
                activity=journey.activity,
            )
        return True

    def ensure_case_access(actor, journey, *, write=False, restricted=False):
        if not _is_service(journey):
            return original_ensure_case_access(actor, journey, write=write, restricted=restricted)
        if not can_access_case(actor, journey, write=write, restricted=restricted):
            raise PermissionDenied("Accès refusé à ce dossier Services.")

    def ensure_case_manager(actor, journey):
        if not _is_service(journey):
            return original_ensure_case_manager(actor, journey)
        _require_service_permission(
            actor,
            journey,
            PermissionCode.ACTIVITY_SERVICES_ASSIGNMENTS_MANAGE,
            require_case_manage=True,
        )

    cs.can_access_case = can_access_case
    cs.ensure_case_access = ensure_case_access
    cs.ensure_case_manager = ensure_case_manager

    def wrap_action(name, permission_code, *, actor_key="actor", journey_getter=None, beneficiary_safe=False, require_case_manage=True):
        original = getattr(cs, name)

        @wraps(original)
        def guarded(*args, **kwargs):
            journey = journey_getter(kwargs) if journey_getter else kwargs.get("journey")
            actor = kwargs.get(actor_key)
            if journey is not None and _is_service(journey):
                if actor is None:
                    raise PermissionDenied("Une mutation de dossier Services exige un acteur explicite.")
                if not (beneficiary_safe and journey.beneficiary_id == _actor_id(actor)):
                    _require_service_permission(
                        actor,
                        journey,
                        permission_code,
                        require_case_manage=require_case_manage,
                    )
            return original(*args, **kwargs)

        setattr(cs, name, guarded)

    step_journey = lambda kw: getattr(kw.get("step"), "journey", None)
    blocker_journey = lambda kw: getattr(kw.get("blocker"), "journey", None)
    assignment_journey = lambda kw: getattr(kw.get("assignment"), "journey", None)
    artifact_journey = lambda kw: getattr(kw.get("artifact"), "journey", None)
    review_journey = lambda kw: getattr(getattr(kw.get("review"), "artifact", None), "journey", None)

    wrap_action("create_step", PermissionCode.ACTIVITY_SERVICES_STEPS_MANAGE, actor_key="created_by")
    for name in ("mark_ready", "start_step", "complete_step", "skip_step", "cancel_step"):
        wrap_action(name, PermissionCode.ACTIVITY_SERVICES_STEPS_MANAGE, journey_getter=step_journey)
    wrap_action("add_step_dependency", PermissionCode.ACTIVITY_SERVICES_STEPS_MANAGE, journey_getter=step_journey)

    wrap_action("create_blocker", PermissionCode.ACTIVITY_SERVICES_BLOCKERS_MANAGE)
    wrap_action("resolve_blocker", PermissionCode.ACTIVITY_SERVICES_BLOCKERS_MANAGE, journey_getter=blocker_journey)

    original_assign_journey = cs.assign_journey

    @wraps(original_assign_journey)
    def assign_journey(*args, **kwargs):
        journey = kwargs["journey"]
        profile = kwargs["profile"]
        responsibility = kwargs["responsibility"]
        if _is_service(journey):
            ensure_case_manager(kwargs["assigned_by"], journey)
            if not _target_has_assignment_authority(profile, journey, responsibility):
                raise ValidationError("Une Assignment Services exige une autorité Services préalable compatible.")
        return original_assign_journey(*args, **kwargs)

    cs.assign_journey = assign_journey
    wrap_action("end_journey_assignment", PermissionCode.ACTIVITY_SERVICES_ASSIGNMENTS_MANAGE, journey_getter=assignment_journey)
    wrap_action("assign_step", PermissionCode.ACTIVITY_SERVICES_ASSIGNMENTS_MANAGE, actor_key="assigned_by", journey_getter=step_journey)

    wrap_action(
        "create_artifact",
        PermissionCode.ACTIVITY_SERVICES_ARTIFACTS_MANAGE,
        actor_key="uploaded_by",
        beneficiary_safe=True,
    )
    wrap_action(
        "create_artifact_version",
        PermissionCode.ACTIVITY_SERVICES_ARTIFACTS_MANAGE,
        actor_key="uploaded_by",
        journey_getter=artifact_journey,
        beneficiary_safe=True,
    )

    @transaction.atomic
    def request_artifact_review(*, artifact, reviewer, requested_by, comment=""):
        if not _is_service(artifact.journey):
            return original_request_artifact_review(
                artifact=artifact,
                reviewer=reviewer,
                requested_by=requested_by,
                comment=comment,
            )
        artifact = (
            JourneyArtifact.objects.select_for_update(of=("self",))
            .select_related("journey", "journey__activity")
            .order_by()
            .get(pk=artifact.pk)
        )
        _require_service_permission(requested_by, artifact.journey, PermissionCode.ACTIVITY_SERVICES_REVIEWS_MANAGE)
        if not can(requested_by, PermissionCode.ACTIVITY_SERVICES_ARTIFACTS_VIEW, activity=artifact.journey.activity):
            raise PermissionDenied("La lecture des documents Services est requise pour demander une revue.")
        if not _active_assignment_exists(reviewer, artifact.journey):
            raise ValidationError("Le reviewer doit avoir une JourneyAssignment active.")
        if service_case_scope(reviewer, artifact.journey) not in {CASE_SCOPE_VIEW_ALL, CASE_SCOPE_VIEW_ASSIGNED}:
            raise ValidationError("Le reviewer n'a plus accès au dossier Services.")
        if not can(reviewer, PermissionCode.ACTIVITY_SERVICES_ARTIFACTS_VIEW, activity=artifact.journey.activity) or not can(
            reviewer,
            PermissionCode.ACTIVITY_SERVICES_REVIEWS_MANAGE,
            activity=artifact.journey.activity,
        ):
            raise ValidationError("Le reviewer doit disposer des permissions Artifact et Review.")
        if artifact.sensitivity == JourneyArtifactSensitivity.RESTRICTED and not can(
            reviewer,
            PermissionCode.ACTIVITY_SERVICES_ARTIFACTS_RESTRICTED_VIEW,
            activity=artifact.journey.activity,
        ):
            raise ValidationError("Le reviewer n'est pas habilité pour ce document restreint.")
        if artifact.status == JourneyArtifactStatus.SUPERSEDED:
            raise ValidationError("Une version remplacée ne peut pas entrer en revue.")
        review = JourneyArtifactReview.objects.create(
            artifact=artifact,
            reviewer=reviewer,
            requested_by=requested_by,
            comment=(comment or "").strip(),
        )
        artifact.status = JourneyArtifactStatus.IN_REVIEW
        artifact._allow_status_transition = True
        artifact.save()
        cs._emit_case_event(
            event_type=cs.DomainEventType.JOURNEY_ARTIFACT_REVIEW_REQUESTED,
            source_type="journey_artifact_review",
            source_id=review.pk,
            journey=artifact.journey,
            suffix="requested",
            payload={"review_id": str(review.pk), "artifact_id": str(artifact.pk), "status": review.status},
        )
        return review

    cs.request_artifact_review = request_artifact_review
    wrap_action("cancel_artifact_review", PermissionCode.ACTIVITY_SERVICES_REVIEWS_MANAGE, journey_getter=review_journey)

    def ensure_reviewer(actor, review):
        if not _is_service(review.artifact.journey):
            return original_ensure_reviewer(actor, review)
        if review.reviewer_id != _actor_id(actor):
            raise PermissionDenied("Seul le reviewer désigné peut décider cette revue.")
        _require_service_permission(actor, review.artifact.journey, PermissionCode.ACTIVITY_SERVICES_REVIEWS_MANAGE)
        if not can(actor, PermissionCode.ACTIVITY_SERVICES_ARTIFACTS_VIEW, activity=review.artifact.journey.activity):
            raise PermissionDenied("La lecture du document Services est requise pour cette revue.")
        if review.artifact.sensitivity == JourneyArtifactSensitivity.RESTRICTED and not can(
            actor,
            PermissionCode.ACTIVITY_SERVICES_ARTIFACTS_RESTRICTED_VIEW,
            activity=review.artifact.journey.activity,
        ):
            raise PermissionDenied("Ce reviewer n'est pas habilité pour le document restreint.")

    cs._ensure_reviewer = ensure_reviewer

    original_create_note = cs.create_note

    @wraps(original_create_note)
    def create_note(*args, **kwargs):
        journey = kwargs["journey"]
        author = kwargs["author"]
        if _is_service(journey) and journey.beneficiary_id != _actor_id(author):
            _require_service_permission(
                author,
                journey,
                PermissionCode.ACTIVITY_SERVICES_NOTES_INTERNAL,
                require_case_manage=True,
            )
        return original_create_note(*args, **kwargs)

    cs.create_note = create_note

    def notes_for_actor(*, actor, journey):
        if not _is_service(journey):
            return original_notes_for_actor(actor=actor, journey=journey)
        if journey.beneficiary_id == _actor_id(actor):
            return JourneyNote.objects.filter(
                journey=journey,
                visibility=JourneyNoteVisibility.BENEFICIARY_VISIBLE,
            ).select_related("author", "step")
        _require_operator_scope(actor, journey)
        queryset = JourneyNote.objects.filter(journey=journey).select_related("author", "step")
        if not can(actor, PermissionCode.ACTIVITY_SERVICES_NOTES_INTERNAL, activity=journey.activity):
            queryset = queryset.filter(visibility=JourneyNoteVisibility.BENEFICIARY_VISIBLE)
        return queryset

    cs.notes_for_actor = notes_for_actor

    def artifacts_for_actor(*, actor, journey):
        if not _is_service(journey):
            return original_artifacts_for_actor(actor=actor, journey=journey)
        queryset = JourneyArtifact.objects.filter(journey=journey).select_related("step", "uploaded_by")
        if journey.beneficiary_id == _actor_id(actor):
            return queryset
        _require_operator_scope(actor, journey)
        if not can(actor, PermissionCode.ACTIVITY_SERVICES_ARTIFACTS_VIEW, activity=journey.activity):
            return queryset.none()
        if not can(actor, PermissionCode.ACTIVITY_SERVICES_ARTIFACTS_RESTRICTED_VIEW, activity=journey.activity):
            queryset = queryset.exclude(sensitivity=JourneyArtifactSensitivity.RESTRICTED)
        return queryset

    cs.artifacts_for_actor = artifacts_for_actor

    def artifact_for_download(*, actor, artifact_id):
        artifact = (
            JourneyArtifact.objects.select_related("journey", "journey__activity", "step", "uploaded_by")
            .filter(pk=artifact_id)
            .first()
        )
        if artifact is None or not _is_service(artifact.journey):
            return original_artifact_for_download(actor=actor, artifact_id=artifact_id)
        if artifact.journey.beneficiary_id == _actor_id(actor):
            return artifact
        _require_service_permission(
            actor,
            artifact.journey,
            PermissionCode.ACTIVITY_SERVICES_ARTIFACTS_VIEW,
            restricted=artifact.sensitivity == JourneyArtifactSensitivity.RESTRICTED,
        )
        return artifact

    cs.artifact_for_download = artifact_for_download
    cs._t34b_service_policy_installed = True
