"""Space applicant access to published Preparation resources.

The Space is the recipient, not the provider. Restricted resources are
never inherited from a coincidental provider-operator role.
"""
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.utils.text import slugify
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ResourceKind, ResourceVisibility
from .services import resources_for_journey
from services.space_beneficiary_api import _journey


def _resources(actor, journey):
    return [
        row for row in resources_for_journey(journey=journey, actor=actor)
        if row.visibility in {
            ResourceVisibility.PUBLIC, ResourceVisibility.PARTICIPANT,
        }
    ]


class SpaceBeneficiaryResourcesAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, slug, journey_id):
        space, journey = _journey(request, slug, journey_id)
        resources = _resources(request.user, journey)
        payload = {
            "space": {"id": str(space.pk), "slug": space.slug},
            "journey_id": str(journey.pk),
            "resources": [
                {
                    "id": str(row.pk),
                    "title": row.title,
                    "description": row.description,
                    "kind": row.kind,
                    "visibility": row.visibility,
                    "version": row.version,
                    "text": row.text_content if row.kind == ResourceKind.TEXT else None,
                    "external_url": row.external_url if row.kind == ResourceKind.URL else None,
                    "mime_type": row.mime_type if row.kind == ResourceKind.FILE else None,
                    "size": row.size if row.kind == ResourceKind.FILE else None,
                    "download_url": (
                        f"/api/v1/organizations/workspaces/{space.slug}/"
                        f"beneficiary/journeys/{journey.pk}/resources/{row.pk}/download/"
                        if row.kind == ResourceKind.FILE else None
                    ),
                }
                for row in resources
            ],
        }
        response = Response(payload)
        response["Cache-Control"] = "private, no-store"
        return response


class SpaceBeneficiaryResourceDownloadAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, slug, journey_id, resource_id):
        _space, journey = _journey(request, slug, journey_id)
        resource = next(
            (row for row in _resources(request.user, journey) if row.pk == resource_id),
            None,
        )
        if resource is None or resource.kind != ResourceKind.FILE or not resource.file:
            raise NotFound()
        try:
            opened = resource.file.open("rb")
        except (FileNotFoundError, OSError):
            raise Http404("Ressource indisponible.") from None
        response = FileResponse(
            opened, as_attachment=True,
            filename=f"{slugify(resource.title) or 'ressource'}-v{resource.version}",
            content_type=resource.mime_type or "application/octet-stream",
        )
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response
