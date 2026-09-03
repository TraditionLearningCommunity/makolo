from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from domain_events.contracts import DomainEventType
from domain_events.services import emit_domain_event

from .models import PlacementAssignment, PlacementPlan, PlacementUnit
from .permissions import user_can_manage_activity_operations


def _require_manage(actor, plan):
    if not actor or not actor.is_authenticated:
        raise PermissionDenied("Authentification requise.")
    if not user_can_manage_activity_operations(actor, plan.occurrence.activity):
        raise PermissionDenied("Vous n’avez pas l’autorité Operations requise pour cette Activity.")


def _subject_kwargs(*, profile=None, external_beneficiary=None):
    if bool(profile) == bool(external_beneficiary):
        raise ValidationError("Le placement doit viser exactement un bénéficiaire, Profile ou externe.")
    return {"profile": profile, "external_beneficiary": external_beneficiary}


def _active_subject_filter(*, profile=None, external_beneficiary=None):
    if profile is not None:
        return {"profile": profile, "ended_at__isnull": True}
    return {"external_beneficiary": external_beneficiary, "ended_at__isnull": True}


def _event_scope(plan):
    activity = plan.occurrence.activity
    return {"space_id": activity.space_id, "activity_id": activity.pk}


def _emit_assigned(assignment):
    plan = assignment.plan
    emit_domain_event(
        event_type=DomainEventType.PLACEMENT_ASSIGNED,
        source_type="placement_assignment",
        source_id=assignment.pk,
        idempotency_key=f"placement:assigned:{assignment.pk}",
        payload={
            "assignment_id": str(assignment.pk),
            "occurrence_id": str(plan.occurrence_id),
            "plan_id": str(plan.pk),
            "unit_id": str(assignment.unit_id),
            "subject_type": "profile" if assignment.profile_id else "external_beneficiary",
        },
        occurred_at=assignment.assigned_at,
        **_event_scope(plan),
    )


def _emit_changed(old_assignment, new_assignment):
    plan = new_assignment.plan
    emit_domain_event(
        event_type=DomainEventType.PLACEMENT_CHANGED,
        source_type="placement_assignment",
        source_id=new_assignment.pk,
        idempotency_key=f"placement:changed:{old_assignment.pk}:{new_assignment.pk}",
        payload={
            "previous_assignment_id": str(old_assignment.pk),
            "assignment_id": str(new_assignment.pk),
            "occurrence_id": str(plan.occurrence_id),
            "plan_id": str(plan.pk),
            "from_unit_id": str(old_assignment.unit_id),
            "to_unit_id": str(new_assignment.unit_id),
            "subject_type": "profile" if new_assignment.profile_id else "external_beneficiary",
        },
        occurred_at=new_assignment.assigned_at,
        **_event_scope(plan),
    )


def _emit_unassigned(assignment):
    plan = assignment.plan
    emit_domain_event(
        event_type=DomainEventType.PLACEMENT_UNASSIGNED,
        source_type="placement_assignment",
        source_id=assignment.pk,
        idempotency_key=f"placement:unassigned:{assignment.pk}",
        payload={
            "assignment_id": str(assignment.pk),
            "occurrence_id": str(plan.occurrence_id),
            "plan_id": str(plan.pk),
            "unit_id": str(assignment.unit_id),
            "subject_type": "profile" if assignment.profile_id else "external_beneficiary",
        },
        occurred_at=assignment.ended_at,
        **_event_scope(plan),
    )


def _lock_plan_and_unit(*, plan_id, unit_id):
    plan = (
        PlacementPlan.objects.select_for_update(of=("self",))
        .select_related("occurrence", "occurrence__activity", "occurrence__activity__space")
        .get(pk=plan_id)
    )
    unit = (
        PlacementUnit.objects.select_for_update(of=("self",))
        .select_related("plan")
        .get(pk=unit_id)
    )
    if unit.plan_id != plan.pk:
        raise ValidationError({"unit": "L’unité n’appartient pas au plan de placement."})
    if not plan.active:
        raise ValidationError({"plan": "Ce plan de placement est inactif."})
    if not unit.active:
        raise ValidationError({"unit": "Cette unité de placement est inactive."})
    return plan, unit


def _ensure_unit_available(unit):
    if unit.exclusive and PlacementAssignment.objects.filter(unit=unit, ended_at__isnull=True).exists():
        raise ValidationError({"unit": "Cette unité exclusive est déjà affectée."})


def _save_assignment(assignment, conflict_message):
    try:
        with transaction.atomic():
            assignment.save()
    except IntegrityError as exc:
        raise ValidationError(conflict_message) from exc


@transaction.atomic
def assign_placement(*, actor, plan, unit, profile=None, external_beneficiary=None):
    subject = _subject_kwargs(profile=profile, external_beneficiary=external_beneficiary)
    plan, unit = _lock_plan_and_unit(plan_id=plan.pk, unit_id=unit.pk)
    _require_manage(actor, plan)

    active_filter = _active_subject_filter(**subject)
    if PlacementAssignment.objects.select_for_update().filter(plan=plan, **active_filter).exists():
        raise ValidationError("Ce bénéficiaire possède déjà un placement actif dans ce plan; utilisez move_placement.")
    _ensure_unit_available(unit)

    assignment = PlacementAssignment(plan=plan, unit=unit, assigned_by=actor, **subject)
    assignment.full_clean()
    _save_assignment(assignment, "Le placement actif est entré en conflit avec une autre affectation.")
    _emit_assigned(assignment)
    return assignment


@transaction.atomic
def move_placement(*, actor, assignment, unit):
    current = (
        PlacementAssignment.objects.select_for_update(of=("self",))
        .select_related(
            "plan",
            "plan__occurrence",
            "plan__occurrence__activity",
            "plan__occurrence__activity__space",
            "unit",
            "profile",
            "external_beneficiary",
        )
        .get(pk=assignment.pk)
    )
    if current.ended_at is not None:
        raise ValidationError("Cette affectation est déjà terminée.")
    plan, target = _lock_plan_and_unit(plan_id=current.plan_id, unit_id=unit.pk)
    _require_manage(actor, plan)
    if target.pk == current.unit_id:
        return current
    _ensure_unit_available(target)

    now = timezone.now()
    current.ended_at = now
    current.full_clean()
    current.save(update_fields=["ended_at"])

    new_assignment = PlacementAssignment(
        plan=plan,
        unit=target,
        profile=current.profile,
        external_beneficiary=current.external_beneficiary,
        assigned_by=actor,
        assigned_at=now,
    )
    new_assignment.full_clean()
    _save_assignment(new_assignment, "Le déplacement est entré en conflit avec une autre affectation.")
    _emit_changed(current, new_assignment)
    return new_assignment


@transaction.atomic
def unassign_placement(*, actor, assignment):
    current = (
        PlacementAssignment.objects.select_for_update(of=("self",))
        .select_related("plan", "plan__occurrence", "plan__occurrence__activity", "plan__occurrence__activity__space")
        .get(pk=assignment.pk)
    )
    _require_manage(actor, current.plan)
    if current.ended_at is not None:
        return current
    current.ended_at = timezone.now()
    current.full_clean()
    current.save(update_fields=["ended_at"])
    _emit_unassigned(current)
    return current


def get_active_placement(*, plan, profile=None, external_beneficiary=None):
    subject = _subject_kwargs(profile=profile, external_beneficiary=external_beneficiary)
    return (
        PlacementAssignment.objects.filter(plan=plan, ended_at__isnull=True, **subject)
        .select_related("plan", "unit", "unit__parent", "profile", "external_beneficiary", "assigned_by")
        .first()
    )
