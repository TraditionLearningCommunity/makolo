from django.shortcuts import get_object_or_404
from django.urls import reverse
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from journeys.models import Journey

from .models import ResourceKind
from .services import resources_for_journey


class JourneyResourceListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, journey_id):
        journey = get_object_or_404(Journey.objects.select_related("activity", "occurrence"), pk=journey_id, beneficiary=request.user)
        resources = resources_for_journey(journey=journey, actor=request.user)
        return Response(
            [
                {
                    "id": str(resource.pk),
                    "title": resource.title,
                    "description": resource.description,
                    "kind": resource.kind,
                    "visibility": resource.visibility,
                    "version": resource.version,
                    "occurrence_id": str(resource.occurrence_id) if resource.occurrence_id else None,
                    "text": resource.text_content if resource.kind == ResourceKind.TEXT else None,
                    "external_url": resource.external_url if resource.kind == ResourceKind.URL else None,
                    "download_url": reverse("preparation:resource-download", kwargs={"resource_id": resource.pk}) if resource.kind == ResourceKind.FILE else None,
                }
                for resource in resources
            ]
        )
