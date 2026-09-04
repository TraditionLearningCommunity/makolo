from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from activities.models import Occurrence

from .offline_action_pack import resolve_offline_action_pack


class OccurrenceOfflineActionPackAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, occurrence_id):
        occurrence = get_object_or_404(
            Occurrence.objects.select_related("activity", "activity__space"),
            pk=occurrence_id,
        )
        payload = resolve_offline_action_pack(occurrence=occurrence, actor=request.user)
        if payload is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(payload)
