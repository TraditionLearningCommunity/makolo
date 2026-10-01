from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from activities.models import Occurrence
from core.api.projections import projection_envelope
from scanner.space_context import build_scanner_context


class ScannerOccurrenceContextAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, occurrence_id):
        observed_at = timezone.now()
        occurrence = get_object_or_404(
            Occurrence.objects.select_related(
                "activity",
                "activity__space",
            ),
            pk=occurrence_id,
        )
        payload = build_scanner_context(
            occurrence=occurrence,
            actor=request.user,
            observed_at=observed_at,
        )
        if payload is None:
            raise NotFound()

        response = Response(
            projection_envelope(
                projection="space.scanner.context",
                data=payload,
                generated_at=observed_at,
                scope="space",
            )
        )
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response
