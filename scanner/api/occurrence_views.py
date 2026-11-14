from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404

from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from activities.models import Occurrence
from scanner.occurrence_access import control_occurrence_access
from scanner.permissions import user_can_scan_activity
from scanner.throttles import ScannerScanThrottle


class OccurrenceScanSerializer(serializers.Serializer):
    token = serializers.CharField(allow_blank=False, max_length=1024, trim_whitespace=True)
    client_reference = serializers.CharField(
        allow_blank=True, required=False, max_length=64, default="",
    )


class ScannerOccurrenceControlAPIView(APIView):
    """A canonical Access control, valid with or without an Event vertical."""
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScannerScanThrottle]

    def post(self, request, occurrence_id):
        occurrence = get_object_or_404(
            Occurrence.objects.select_related("activity", "activity__space"),
            pk=occurrence_id,
        )
        if not user_can_scan_activity(request.user, occurrence.activity, occurrence=occurrence):
            raise NotFound()

        serializer = OccurrenceScanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = control_occurrence_access(
                occurrence=occurrence,
                actor=request.user,
                token=serializer.validated_data["token"],
                client_reference=serializer.validated_data["client_reference"],
            )
        except DjangoPermissionDenied as exc:
            raise PermissionDenied(str(exc)) from exc
        except DjangoValidationError as exc:
            raise serializers.ValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            ) from exc

        response = Response(result)
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response
