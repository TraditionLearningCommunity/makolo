"""Bearer-authenticated streaming of existing Journey artifacts used by Now.

The Journey owns the file and authorization. Now only references it.
"""
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from journeys.collaboration_services import artifact_for_download


class PersonalNowJourneyArtifactMediaAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, artifact_id):
        try:
            artifact = artifact_for_download(
                actor=request.user, artifact_id=artifact_id,
            )
        except PermissionDenied as exc:
            raise Http404 from exc
        if not artifact.file:
            raise Http404

        response = FileResponse(
            artifact.file.open("rb"),
            content_type=artifact.mime_type or "application/octet-stream",
            as_attachment=False,
        )
        response["Content-Disposition"] = "inline"
        response["X-Content-Type-Options"] = "nosniff"
        response["Cache-Control"] = "private, no-store"
        return response
