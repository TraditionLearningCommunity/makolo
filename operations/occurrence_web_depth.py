"""L5 Web depth adapters. Never bypass canonical owners for a mutation."""
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404

from journeys.models import ExternalBeneficiary

from .experience_insights import resolve_occurrence_insight
from .models import OccurrenceCheckpoint, OccurrenceQueue, PlacementAssignment, PlacementPlan, PlacementUnit, QueueEntry
from .permissions import user_can_manage_activity_operations
from .queue_services import call_next, close_queue, pause_queue, resume_queue, cancel_entry
from .checkpoint_services import open_checkpoint, pause_checkpoint, resume_checkpoint, close_checkpoint
from .placement_services import assign_placement, unassign_placement, move_placement

User = get_user_model()


def depth_page(*, occurrence, actor, projection, kind):
    item = next((d for d in projection.get("depths", ()) if d["kind"] == kind), None)
    if item is None:
        raise Http404
    sections = projection.get("sections") or {}
    if kind in {"capacity", "finance", "commerce", "places"}:
        result = resolve_occurrence_insight(
            occurrence=occurrence, viewer=actor, kind=kind,
            organizer_scope=True,
        )
        if result is None:
            raise Http404
        rows = (
            result.get("entries") or result.get("offers") or
            result.get("payments") or result.get("obligations") or
            result.get("order_counts") or []
        )
        return {"depth": item, "rows": rows, "details": result}
    if kind == "scanner":
        raise Http404
    participant = sections.get("participant") or {}
    operator = sections.get("organizer") or sections.get("platform") or {}
    if kind == "my_queue":
        rows = participant.get("queue") or []
    elif kind == "my_placement":
        rows = participant.get("placement") or []
    elif kind == "my_checkpoints":
        rows = (participant.get("checkpoints") or {}).get("items") or []
    elif kind == "operator_queue":
        rows = operator.get("queue") or []
    elif kind == "operator_placement":
        from .placement_selectors import get_operator_placement_plans

        rows = []
        for plan in get_operator_placement_plans(actor, occurrence):
            units = []
            for unit in plan.units.all():
                units.append({
                    "id": str(unit.pk), "label": unit.label,
                    "kind": unit.kind,
                    "assignments": [
                        {
                            "id": str(assignment.pk),
                            "beneficiary": assignment.beneficiary_display_name,
                        }
                        for assignment in plan.active_assignments
                        if assignment.unit_id == unit.pk
                    ],
                })
            rows.append({
                "id": str(plan.pk), "label": plan.label,
                "active": plan.active, "units": units,
            })
    elif kind == "operator_checkpoints":
        rows = operator.get("checkpoints") or []
    elif kind == "readiness":
        # One person may be a participant and an operator. The advertised
        # readiness depth belongs to its declared territory, not whichever
        # backend section happens to be populated first.
        facts = (
            participant.get("readiness") or {}
            if item.get("territory") == "participant"
            else operator.get("operational_readiness") or {}
        )
        if "contributors" in facts:
            rows = facts.get("contributors") or []
        else:
            # Personal Jour J groups owner checks by their effect, while the
            # operator's projection exposes flat contributors. Keep both.
            rows = [
                {
                    "label": check.get("summary") or check.get("key") or "Préparation",
                    "state": check.get("state") or state,
                    "reason": check.get("reason"),
                    "source": check.get("source"),
                }
                for group, state in (
                    ("blockers", "blocking"),
                    ("actor_interventions", "action_required"),
                    ("waiting", "waiting"),
                    ("ready", "satisfied"),
                )
                for check in facts.get(group, [])
            ]
    else:
        raise Http404
    return {"depth": item, "rows": rows, "details": {}}


def execute_depth_action(*, occurrence, actor, projection, kind, submitted):
    item = next((d for d in projection.get("depths", ()) if d["kind"] == kind), None)
    if item is None:
        raise Http404
    action = (submitted.get("action") or "").strip()
    if kind == "my_queue" and action == "cancel":
        entry = QueueEntry.objects.select_related(
            "queue", "queue__occurrence", "queue__occurrence__activity"
        ).filter(
            pk=submitted.get("item_id"), queue__occurrence=occurrence, profile=actor,
        ).first()
        if entry is None:
            raise Http404
        return cancel_entry(actor=actor, entry=entry, allow_self=True)

    if not item.get("can_manage") or not user_can_manage_activity_operations(
        actor, occurrence.activity,
    ):
        raise PermissionDenied("Droit de modification Operations requis.")

    if kind == "operator_queue":
        queue = OccurrenceQueue.objects.select_related(
            "occurrence", "occurrence__activity",
        ).filter(
            pk=submitted.get("item_id"), occurrence=occurrence,
        ).first()
        if queue is None:
            raise Http404
        if action == "call":
            return call_next(actor=actor, queue=queue)
        service = {
            "pause": pause_queue, "resume": resume_queue, "close": close_queue,
        }.get(action)
        if service:
            return service(actor=actor, queue=queue)

    if kind == "operator_checkpoints":
        checkpoint = OccurrenceCheckpoint.objects.select_related(
            "occurrence", "occurrence__activity",
        ).filter(
            pk=submitted.get("item_id"), occurrence=occurrence,
        ).first()
        if checkpoint is None:
            raise Http404
        service = {
            "open": open_checkpoint,
            "pause": pause_checkpoint,
            "resume": resume_checkpoint,
            "close": close_checkpoint,
        }.get(action)
        if service:
            return service(actor=actor, checkpoint=checkpoint)

    if kind == "operator_placement":
        if action == "assign":
            plan = PlacementPlan.objects.filter(
                pk=submitted.get("item_id"), occurrence=occurrence,
            ).first()
            unit = PlacementUnit.objects.filter(
                pk=submitted.get("unit_id"), plan=plan,
            ).first() if plan else None
            if plan is None or unit is None:
                raise Http404
            profile_id = (submitted.get("profile_id") or "").strip()
            external_id = (submitted.get("external_beneficiary_id") or "").strip()
            if bool(profile_id) == bool(external_id):
                raise ValidationError("Un seul bénéficiaire est requis.")
            profile = User.objects.filter(pk=profile_id).first() if profile_id else None
            external = ExternalBeneficiary.objects.filter(pk=external_id).first() if external_id else None
            if profile is None and external is None:
                raise Http404
            from .placement_selectors import (
                profile_is_placement_candidate,
                external_beneficiary_is_placement_candidate,
            )
            if profile is not None and not profile_is_placement_candidate(profile, occurrence):
                raise ValidationError("Ce Profil n'est pas bénéficiaire de l'Occurrence.")
            if external is not None and not external_beneficiary_is_placement_candidate(
                external, occurrence,
            ):
                raise ValidationError("Ce bénéficiaire externe n'est pas lié à l'Occurrence.")
            return assign_placement(
                actor=actor, plan=plan, unit=unit,
                profile=profile, external_beneficiary=external,
            )
        if action in {"unassign", "move"}:
            assignment = PlacementAssignment.objects.select_related(
                "plan", "plan__occurrence", "unit",
            ).filter(
                pk=submitted.get("item_id"), plan__occurrence=occurrence,
            ).first()
            if assignment is None:
                raise Http404
            if action == "unassign":
                return unassign_placement(actor=actor, assignment=assignment)
            unit = PlacementUnit.objects.filter(
                pk=submitted.get("unit_id"), plan=assignment.plan,
            ).first()
            if unit is None:
                raise Http404
            return move_placement(actor=actor, assignment=assignment, unit=unit)
    raise Http404
