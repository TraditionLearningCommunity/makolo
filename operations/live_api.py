from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from activities.models import Occurrence

from .occurrence_live import resolve_occurrence_live, resolve_occurrence_readiness_for_viewer


def _occurrence(occurrence_id):
    return get_object_or_404(
        Occurrence.objects.select_related("activity", "activity__space"),
        pk=occurrence_id,
    )


class OccurrenceOperationalReadinessAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, occurrence_id):
        occurrence = _occurrence(occurrence_id)
        payload = resolve_occurrence_readiness_for_viewer(occurrence=occurrence, actor=request.user)
        if payload is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(payload)


class OccurrenceLiveAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, occurrence_id):
        occurrence = _occurrence(occurrence_id)
        payload = resolve_occurrence_live(occurrence=occurrence, actor=request.user)
        if payload is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(payload)
