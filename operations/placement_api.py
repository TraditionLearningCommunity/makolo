from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from activities.models import Occurrence
from journeys.models import ExternalBeneficiary

from .models import PlacementPlan, PlacementUnit
from .placement_selectors import (
    external_beneficiary_is_placement_candidate,
    get_operator_placement_assignment,
    get_operator_placement_plans,
    get_profile_occurrence_placements,
    profile_is_placement_candidate,
)
from .placement_services import assign_placement, move_placement, unassign_placement


User = get_user_model()


def _unit_path(unit):
    labels = []
    seen = set()
    current = unit
    while current is not None and current.pk not in seen:
        seen.add(current.pk)
        labels.append(current.label)
        current = current.parent
    return list(reversed(labels))


def _assignment_payload(assignment):
    return {
        "id": assignment.pk,
        "plan_id": assignment.plan_id,
        "plan_key": assignment.plan.key,
        "plan_label": assignment.plan.label,
        "unit_id": assignment.unit_id,
        "unit_key": assignment.unit.key,
        "unit_label": assignment.unit.label,
        "unit_path": _unit_path(assignment.unit),
        "beneficiary": {
            "type": "profile" if assignment.profile_id else "external_beneficiary",
            "id": assignment.profile_id or assignment.external_beneficiary_id,
            "display_name": assignment.beneficiary_display_name,
        },
        "assigned_by_id": assignment.assigned_by_id,
        "assigned_at": assignment.assigned_at,
        "ended_at": assignment.ended_at,
    }


def _raise_drf_validation(exc):
    if hasattr(exc, "message_dict"):
        raise serializers.ValidationError(exc.message_dict)
    raise serializers.ValidationError(exc.messages)


class PlacementAssignSerializer(serializers.Serializer):
    unit_id = serializers.UUIDField()
    profile_id = serializers.UUIDField(required=False, allow_null=True)
    external_beneficiary_id = serializers.UUIDField(required=False, allow_null=True)

    def validate(self, attrs):
        if bool(attrs.get("profile_id")) == bool(attrs.get("external_beneficiary_id")):
            raise serializers.ValidationError("Fournissez exactement un Profile ou un ExternalBeneficiary.")
        return attrs


class PlacementMoveSerializer(serializers.Serializer):
    unit_id = serializers.UUIDField()


class MyOccurrencePlacementsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, occurrence_id):
        occurrence = get_object_or_404(Occurrence.objects.select_related("activity"), pk=occurrence_id)
        assignments = get_profile_occurrence_placements(request.user, occurrence)
        return Response([_assignment_payload(row) for row in assignments])


class OperatorOccurrencePlacementPlansAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, occurrence_id):
        occurrence = get_object_or_404(Occurrence.objects.select_related("activity", "activity__space"), pk=occurrence_id)
        plans = get_operator_placement_plans(request.user, occurrence)
        if not plans.exists():
            from operations.permissions import user_can_view_activity_operations

            if not user_can_view_activity_operations(request.user, occurrence.activity):
                return Response(status=status.HTTP_403_FORBIDDEN)
        data = []
        for plan in plans:
            assignments_by_unit = {}
            for assignment in plan.active_assignments:
                assignments_by_unit.setdefault(assignment.unit_id, []).append(_assignment_payload(assignment))
            data.append(
                {
                    "id": plan.pk,
                    "key": plan.key,
                    "label": plan.label,
                    "required": plan.required,
                    "active": plan.active,
                    "units": [
                        {
                            "id": unit.pk,
                            "key": unit.key,
                            "label": unit.label,
                            "kind": unit.kind,
                            "parent_id": unit.parent_id,
                            "path": _unit_path(unit),
                            "position": unit.position,
                            "active": unit.active,
                            "exclusive": unit.exclusive,
                            "assignments": assignments_by_unit.get(unit.pk, []),
                        }
                        for unit in plan.units.all()
                    ],
                }
            )
        return Response(data)


class PlacementAssignmentsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, plan_id):
        plan = get_object_or_404(
            PlacementPlan.objects.select_related("occurrence", "occurrence__activity", "occurrence__activity__space"),
            pk=plan_id,
        )
        from operations.permissions import user_can_manage_activity_operations

        if not user_can_manage_activity_operations(request.user, plan.occurrence.activity):
            return Response(status=status.HTTP_403_FORBIDDEN)
        serializer = PlacementAssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        unit = get_object_or_404(PlacementUnit, pk=serializer.validated_data["unit_id"], plan=plan)

        profile = None
        external = None
        profile_id = serializer.validated_data.get("profile_id")
        external_id = serializer.validated_data.get("external_beneficiary_id")
        if profile_id:
            profile = get_object_or_404(User, pk=profile_id)
            if not profile_is_placement_candidate(profile, plan.occurrence):
                raise serializers.ValidationError({"profile_id": "Ce Profile n’est pas un bénéficiaire de cette Occurrence."})
        else:
            external = get_object_or_404(ExternalBeneficiary, pk=external_id)
            if not external_beneficiary_is_placement_candidate(external, plan.occurrence):
                raise serializers.ValidationError(
                    {"external_beneficiary_id": "Ce bénéficiaire externe n’est pas lié à cette Occurrence."}
                )
        try:
            assignment = assign_placement(
                actor=request.user,
                plan=plan,
                unit=unit,
                profile=profile,
                external_beneficiary=external,
            )
        except DjangoValidationError as exc:
            _raise_drf_validation(exc)
        return Response(_assignment_payload(assignment), status=status.HTTP_201_CREATED)


class PlacementAssignmentDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, assignment_id):
        assignment = get_operator_placement_assignment(request.user, assignment_id)
        if assignment is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        serializer = PlacementMoveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        unit = get_object_or_404(PlacementUnit, pk=serializer.validated_data["unit_id"], plan=assignment.plan)
        try:
            moved = move_placement(actor=request.user, assignment=assignment, unit=unit)
        except DjangoValidationError as exc:
            _raise_drf_validation(exc)
        return Response(_assignment_payload(moved))

    def delete(self, request, assignment_id):
        assignment = get_operator_placement_assignment(request.user, assignment_id)
        if assignment is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        try:
            unassign_placement(actor=request.user, assignment=assignment)
        except DjangoValidationError as exc:
            _raise_drf_validation(exc)
        return Response(status=status.HTTP_204_NO_CONTENT)
