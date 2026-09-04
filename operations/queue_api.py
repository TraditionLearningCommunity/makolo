from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from activities.models import Occurrence
from journeys.models import ExternalBeneficiary

from .checkpoint_selectors import profile_is_checkpoint_beneficiary
from .models import OccurrenceCheckpoint, OccurrenceQueue, QueueEntry
from .permissions import user_can_manage_activity_operations, user_can_view_activity_operations
from .queue_selectors import active_entries, my_queue_entries, queue_position, queue_snapshot, queues_for_occurrence
from .queue_services import (
    call_next,
    cancel_entry,
    close_queue,
    enter_queue,
    expire_entry,
    pause_queue,
    resume_queue,
    serve_entry,
)


User = get_user_model()


def _raise_drf_validation(exc):
    if hasattr(exc, "message_dict"):
        raise serializers.ValidationError(exc.message_dict)
    raise serializers.ValidationError(exc.messages)


def _queue_payload(queue):
    snapshot = queue_snapshot(queue=queue)
    return {
        "id": queue.pk,
        "occurrence_id": queue.occurrence_id,
        "checkpoint_id": queue.checkpoint_id,
        "key": queue.key,
        "label": queue.label,
        "status": queue.status,
        "counts": snapshot,
    }


def _entry_payload(entry, *, include_position=False):
    payload = {
        "id": entry.pk,
        "queue_id": entry.queue_id,
        "status": entry.status,
        "sequence": entry.sequence,
        "beneficiary": {
            "type": "profile" if entry.profile_id else "external_beneficiary",
            "id": entry.profile_id or entry.external_beneficiary_id,
        },
        "entered_at": entry.entered_at,
        "called_at": entry.called_at,
        "served_at": entry.served_at,
        "ended_at": entry.ended_at,
    }
    if include_position:
        payload["position"] = queue_position(entry=entry)
    return payload


def _operator_queue(user, queue_id, *, manage=False):
    queue = OccurrenceQueue.objects.select_related(
        "occurrence", "occurrence__activity", "occurrence__activity__space", "checkpoint"
    ).filter(pk=queue_id).first()
    if queue is None:
        return None
    allowed = (
        user_can_manage_activity_operations(user, queue.occurrence.activity)
        if manage
        else user_can_view_activity_operations(user, queue.occurrence.activity)
    )
    return queue if allowed else None


def _operator_entry(user, entry_id, *, manage=False):
    entry = QueueEntry.objects.select_related(
        "queue", "queue__occurrence", "queue__occurrence__activity", "queue__occurrence__activity__space", "queue__checkpoint"
    ).filter(pk=entry_id).first()
    if entry is None:
        return None
    allowed = (
        user_can_manage_activity_operations(user, entry.queue.occurrence.activity)
        if manage
        else user_can_view_activity_operations(user, entry.queue.occurrence.activity)
    )
    return entry if allowed else None


class QueueCreateSerializer(serializers.Serializer):
    key = serializers.CharField(max_length=80)
    label = serializers.CharField(max_length=180)
    checkpoint_id = serializers.UUIDField(required=False, allow_null=True)


class QueueEnterSerializer(serializers.Serializer):
    profile_id = serializers.UUIDField(required=False, allow_null=True)
    external_beneficiary_id = serializers.UUIDField(required=False, allow_null=True)
    source = serializers.CharField(required=False, allow_blank=True, max_length=80, default="operator")
    client_reference = serializers.CharField(required=False, allow_blank=True, max_length=64, default="")

    def validate(self, attrs):
        if bool(attrs.get("profile_id")) == bool(attrs.get("external_beneficiary_id")):
            raise serializers.ValidationError("Fournissez exactement un Profile ou un ExternalBeneficiary.")
        return attrs


class SelfQueueEnterSerializer(serializers.Serializer):
    source = serializers.CharField(required=False, allow_blank=True, max_length=80, default="participant")
    client_reference = serializers.CharField(required=False, allow_blank=True, max_length=64, default="")


class QueueStatusSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["pause", "resume", "close"])


class OperatorOccurrenceQueuesAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, occurrence_id):
        occurrence = get_object_or_404(Occurrence.objects.select_related("activity", "activity__space"), pk=occurrence_id)
        if not user_can_view_activity_operations(request.user, occurrence.activity):
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response([_queue_payload(queue) for queue in queues_for_occurrence(occurrence=occurrence)])

    def post(self, request, occurrence_id):
        occurrence = get_object_or_404(Occurrence.objects.select_related("activity", "activity__space"), pk=occurrence_id)
        if not user_can_manage_activity_operations(request.user, occurrence.activity):
            return Response(status=status.HTTP_404_NOT_FOUND)
        serializer = QueueCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        checkpoint = None
        checkpoint_id = serializer.validated_data.get("checkpoint_id")
        if checkpoint_id:
            checkpoint = OccurrenceCheckpoint.objects.filter(pk=checkpoint_id, occurrence=occurrence).first()
            if checkpoint is None:
                return Response(status=status.HTTP_404_NOT_FOUND)
        queue = OccurrenceQueue(
            occurrence=occurrence,
            checkpoint=checkpoint,
            key=serializer.validated_data["key"],
            label=serializer.validated_data["label"],
        )
        try:
            queue.save()
        except DjangoValidationError as exc:
            _raise_drf_validation(exc)
        return Response(_queue_payload(queue), status=status.HTTP_201_CREATED)


class MyOccurrenceQueuesAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, occurrence_id):
        occurrence = get_object_or_404(Occurrence.objects.select_related("activity"), pk=occurrence_id)
        entries = my_queue_entries(profile=request.user, occurrence=occurrence)
        if not entries.exists() and not profile_is_checkpoint_beneficiary(request.user, occurrence):
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response([_entry_payload(entry, include_position=True) for entry in entries])


class QueueEntriesAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, queue_id):
        queue = _operator_queue(request.user, queue_id)
        if queue is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response([_entry_payload(entry, include_position=True) for entry in active_entries(queue=queue)])

    def post(self, request, queue_id):
        queue = _operator_queue(request.user, queue_id, manage=True)
        if queue is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        serializer = QueueEnterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile = None
        external = None
        if serializer.validated_data.get("profile_id"):
            profile = get_object_or_404(User, pk=serializer.validated_data["profile_id"])
        else:
            external = get_object_or_404(ExternalBeneficiary, pk=serializer.validated_data["external_beneficiary_id"])
        try:
            entry = enter_queue(
                actor=request.user,
                queue=queue,
                profile=profile,
                external_beneficiary=external,
                source=serializer.validated_data.get("source", "operator"),
                client_reference=serializer.validated_data.get("client_reference", ""),
            )
        except DjangoValidationError as exc:
            _raise_drf_validation(exc)
        return Response(_entry_payload(entry, include_position=True), status=status.HTTP_201_CREATED)


class MyQueueEntryAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, queue_id):
        queue = OccurrenceQueue.objects.select_related("occurrence", "occurrence__activity", "checkpoint").filter(pk=queue_id).first()
        if queue is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        serializer = SelfQueueEnterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            entry = enter_queue(
                actor=request.user,
                queue=queue,
                profile=request.user,
                source=serializer.validated_data.get("source", "participant"),
                client_reference=serializer.validated_data.get("client_reference", ""),
                allow_self=True,
            )
        except DjangoValidationError as exc:
            _raise_drf_validation(exc)
        return Response(_entry_payload(entry, include_position=True), status=status.HTTP_201_CREATED)


class QueueCallNextAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, queue_id):
        queue = _operator_queue(request.user, queue_id, manage=True)
        if queue is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        try:
            entry = call_next(actor=request.user, queue=queue)
        except DjangoValidationError as exc:
            _raise_drf_validation(exc)
        if entry is None:
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(_entry_payload(entry))


class QueueStatusAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, queue_id):
        queue = _operator_queue(request.user, queue_id, manage=True)
        if queue is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        serializer = QueueStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        service = {"pause": pause_queue, "resume": resume_queue, "close": close_queue}[serializer.validated_data["action"]]
        try:
            queue = service(actor=request.user, queue=queue)
        except DjangoValidationError as exc:
            _raise_drf_validation(exc)
        return Response(_queue_payload(queue))


class QueueEntryActionAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, entry_id, action):
        entry = _operator_entry(request.user, entry_id, manage=True)
        if entry is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        service = {
            "serve": serve_entry,
            "expire": expire_entry,
            "cancel": cancel_entry,
        }.get(action)
        if service is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        try:
            entry = service(actor=request.user, entry=entry)
        except DjangoValidationError as exc:
            _raise_drf_validation(exc)
        return Response(_entry_payload(entry))


class MyQueueEntryCancelAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, entry_id):
        entry = QueueEntry.objects.select_related(
            "queue", "queue__occurrence", "queue__occurrence__activity", "queue__checkpoint"
        ).filter(pk=entry_id, profile=request.user).first()
        if entry is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        try:
            entry = cancel_entry(actor=request.user, entry=entry, allow_self=True)
        except DjangoValidationError as exc:
            _raise_drf_validation(exc)
        return Response(_entry_payload(entry))
