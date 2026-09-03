from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from access.models import AccessUse
from activities.models import Occurrence
from journeys.models import ExternalBeneficiary

from .checkpoint_selectors import active_checkpoint_assignments, next_checkpoint, observations_for_beneficiary, ordered_checkpoints
from .checkpoint_services import (
    assign_checkpoint_operator,
    close_checkpoint,
    end_checkpoint_assignment,
    observe_checkpoint,
    open_checkpoint,
    pause_checkpoint,
    resume_checkpoint,
)
from .models import CheckpointAssignment, OccurrenceCheckpoint
from .permissions import user_can_manage_activity_operations, user_can_view_activity_operations
from .placement_selectors import external_beneficiary_is_placement_candidate, profile_is_placement_candidate


User = get_user_model()


def _raise_drf_validation(exc):
    if hasattr(exc, "message_dict"):
        raise serializers.ValidationError(exc.message_dict)
    raise serializers.ValidationError(exc.messages)


def _checkpoint_payload(checkpoint):
    return {
        "id": checkpoint.pk,
        "key": checkpoint.key,
        "label": checkpoint.label,
        "description": checkpoint.description,
        "position": checkpoint.position,
        "required": checkpoint.required,
        "status": checkpoint.status,
        "active": checkpoint.active,
    }


def _operator_checkpoint(user, checkpoint_id, *, manage=False):
    checkpoint = OccurrenceCheckpoint.objects.select_related(
        "occurrence", "occurrence__activity", "occurrence__activity__space"
    ).filter(pk=checkpoint_id).first()
    if checkpoint is None:
        return None
    allowed = (
        user_can_manage_activity_operations(user, checkpoint.occurrence.activity)
        if manage
        else user_can_view_activity_operations(user, checkpoint.occurrence.activity)
    )
    return checkpoint if allowed else None


class CheckpointObservationSerializer(serializers.Serializer):
    profile_id = serializers.UUIDField(required=False, allow_null=True)
    external_beneficiary_id = serializers.UUIDField(required=False, allow_null=True)
    source = serializers.CharField(required=False, allow_blank=True, max_length=80, default="operator")
    client_reference = serializers.CharField(required=False, allow_blank=True, max_length=64, default="")
    access_use_id = serializers.UUIDField(required=False, allow_null=True)

    def validate(self, attrs):
        if bool(attrs.get("profile_id")) == bool(attrs.get("external_beneficiary_id")):
            raise serializers.ValidationError("Fournissez exactement un Profile ou un ExternalBeneficiary.")
        return attrs


class CheckpointAssignmentSerializer(serializers.Serializer):
    profile_id = serializers.UUIDField()


class CheckpointStatusSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["open", "pause", "resume", "close"])


class OperatorOccurrenceCheckpointsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, occurrence_id):
        occurrence = get_object_or_404(Occurrence.objects.select_related("activity", "activity__space"), pk=occurrence_id)
        if not user_can_view_activity_operations(request.user, occurrence.activity):
            return Response(status=status.HTTP_404_NOT_FOUND)
        data = []
        for checkpoint in ordered_checkpoints(occurrence=occurrence).prefetch_related("assignments__profile"):
            row = _checkpoint_payload(checkpoint)
            row["assignments"] = [
                {
                    "id": assignment.pk,
                    "profile_id": assignment.profile_id,
                    "display_name": assignment.profile.get_full_name().strip() or assignment.profile.username,
                    "assigned_at": assignment.assigned_at,
                }
                for assignment in active_checkpoint_assignments(checkpoint=checkpoint)
            ]
            data.append(row)
        return Response(data)


class MyOccurrenceCheckpointsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, occurrence_id):
        occurrence = get_object_or_404(Occurrence.objects.select_related("activity"), pk=occurrence_id)
        if not profile_is_placement_candidate(request.user, occurrence):
            return Response(status=status.HTTP_404_NOT_FOUND)
        completed = {
            row.checkpoint_id: row
            for row in observations_for_beneficiary(occurrence=occurrence, profile=request.user)
        }
        next_result = next_checkpoint(occurrence=occurrence, profile=request.user)
        return Response(
            [
                {
                    "checkpoint": _checkpoint_payload(checkpoint),
                    "completed": checkpoint.pk in completed,
                    "observed_at": completed[checkpoint.pk].observed_at if checkpoint.pk in completed else None,
                    "next": bool(next_result.checkpoint and next_result.checkpoint.pk == checkpoint.pk),
                    "blocked_reason": next_result.blocked_reason if next_result.checkpoint and next_result.checkpoint.pk == checkpoint.pk else "",
                }
                for checkpoint in ordered_checkpoints(occurrence=occurrence)
            ]
        )


class CheckpointStatusAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, checkpoint_id):
        checkpoint = _operator_checkpoint(request.user, checkpoint_id, manage=True)
        if checkpoint is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        serializer = CheckpointStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        service = {
            "open": open_checkpoint,
            "pause": pause_checkpoint,
            "resume": resume_checkpoint,
            "close": close_checkpoint,
        }[serializer.validated_data["action"]]
        try:
            checkpoint = service(actor=request.user, checkpoint=checkpoint)
        except DjangoValidationError as exc:
            _raise_drf_validation(exc)
        return Response(_checkpoint_payload(checkpoint))


class CheckpointAssignmentsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, checkpoint_id):
        checkpoint = _operator_checkpoint(request.user, checkpoint_id, manage=True)
        if checkpoint is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        serializer = CheckpointAssignmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile = get_object_or_404(User, pk=serializer.validated_data["profile_id"])
        try:
            assignment = assign_checkpoint_operator(actor=request.user, checkpoint=checkpoint, profile=profile)
        except DjangoValidationError as exc:
            _raise_drf_validation(exc)
        return Response(
            {"id": assignment.pk, "checkpoint_id": assignment.checkpoint_id, "profile_id": assignment.profile_id, "assigned_at": assignment.assigned_at},
            status=status.HTTP_201_CREATED,
        )


class CheckpointAssignmentDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, assignment_id):
        assignment = CheckpointAssignment.objects.select_related(
            "checkpoint", "checkpoint__occurrence", "checkpoint__occurrence__activity", "checkpoint__occurrence__activity__space"
        ).filter(pk=assignment_id).first()
        if assignment is None or not user_can_manage_activity_operations(request.user, assignment.checkpoint.occurrence.activity):
            return Response(status=status.HTTP_404_NOT_FOUND)
        try:
            end_checkpoint_assignment(actor=request.user, assignment=assignment)
        except DjangoValidationError as exc:
            _raise_drf_validation(exc)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CheckpointObservationsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, checkpoint_id):
        checkpoint = _operator_checkpoint(request.user, checkpoint_id, manage=True)
        if checkpoint is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        serializer = CheckpointObservationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile = None
        external = None
        if serializer.validated_data.get("profile_id"):
            profile = get_object_or_404(User, pk=serializer.validated_data["profile_id"])
            if not profile_is_placement_candidate(profile, checkpoint.occurrence):
                raise serializers.ValidationError({"profile_id": "Ce Profile n’est pas un bénéficiaire de cette Occurrence."})
        else:
            external = get_object_or_404(ExternalBeneficiary, pk=serializer.validated_data["external_beneficiary_id"])
            if not external_beneficiary_is_placement_candidate(external, checkpoint.occurrence):
                raise serializers.ValidationError({"external_beneficiary_id": "Ce bénéficiaire externe n’est pas lié à cette Occurrence."})
        access_use = None
        if serializer.validated_data.get("access_use_id"):
            access_use = AccessUse.objects.select_related("access").filter(pk=serializer.validated_data["access_use_id"]).first()
            if access_use is None:
                return Response(status=status.HTTP_404_NOT_FOUND)
        try:
            observation = observe_checkpoint(
                actor=request.user,
                checkpoint=checkpoint,
                profile=profile,
                external_beneficiary=external,
                source=serializer.validated_data.get("source", "operator"),
                client_reference=serializer.validated_data.get("client_reference", ""),
                access_use=access_use,
            )
        except DjangoValidationError as exc:
            _raise_drf_validation(exc)
        return Response(
            {
                "id": observation.pk,
                "checkpoint_id": observation.checkpoint_id,
                "beneficiary": {
                    "type": "profile" if observation.profile_id else "external_beneficiary",
                    "id": observation.profile_id or observation.external_beneficiary_id,
                },
                "observed_at": observation.observed_at,
                "access_use_id": observation.access_use_id,
            },
            status=status.HTTP_201_CREATED,
        )
