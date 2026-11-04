"""Private recipient download for an explicit immutable document share."""
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import FileResponse, Http404
from django.core.exceptions import PermissionDenied
from django.utils.text import slugify
from django.views import View
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from .services import ShareUnavailable
from .space_document_sharing import space_document_delivery


def _download_for(user, delivery_id):
    try:
        _, version = space_document_delivery(
            user=user, delivery_id=delivery_id, mark_opened=True,
        )
    except (ShareUnavailable, PermissionDenied) as exc:
        # A forged or revoked grant must never reveal whether a file exists.
        # Authentication and recipient identity are verified by Sharing.
        raise Http404 from exc
    response = FileResponse(
        version.file.open("rb"), as_attachment=True,
        filename=f"{slugify(version.document.title) or 'document'}-v{version.version}",
        content_type=version.mime_type,
    )
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    response["Referrer-Policy"] = "no-referrer"
    return response


class SpaceDocumentShareDownloadView(LoginRequiredMixin, View):
    login_url = "core:login"

    def get(self, request, delivery_id):
        return _download_for(request.user, delivery_id)


class SpaceDocumentShareDownloadAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, delivery_id):
        return _download_for(request.user, delivery_id)
