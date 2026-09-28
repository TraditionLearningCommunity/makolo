from __future__ import annotations

from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from authorization.constants import PermissionCode
from authorization.selectors import has_direct_space_permission
from authorization.services import can
from intelligence.interoperability import (
    platform_provider_connections,
    project_provider_connection,
    provider_connections_for_space,
)
from organizations.models import Organization

from .profile_projection import build_profile_interoperability_payload
from .projections import build_interoperability_payload


def _private_response(payload):
    response = Response(payload)
    response["Cache-Control"] = "private, no-store"
    return response


class PersonalInteroperabilityAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return _private_response(build_profile_interoperability_payload(request.user))


class SpaceInteroperabilityAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, slug):
        space = Organization.objects.filter(slug=slug).first()
        if space is None or not has_direct_space_permission(
            request.user, space, PermissionCode.SPACE_MANAGE
        ):
            raise NotFound()

        connections = [
            project_provider_connection(connection, manageable=True)
            for connection in provider_connections_for_space(space)
        ]
        return _private_response(
            build_interoperability_payload(
                context="space",
                connections=connections,
                self_link=f"/api/v1/organizations/workspaces/{space.slug}/interoperability/",
                actor=request.user,
                authority_context=space,
            )
        )


class PlatformInteroperabilityAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not can(request.user, PermissionCode.PLATFORM_MANAGE):
            raise PermissionDenied("Autorité Platform requise.")

        connections = [
            project_provider_connection(connection, manageable=True)
            for connection in platform_provider_connections()
        ]
        payload = build_interoperability_payload(
            context="platform",
            connections=connections,
            self_link="/api/v1/platform/interoperability/",
            actor=request.user,
            authority_context="platform",
        )
        payload["space_modules_included"] = False
        payload["personal_modules_included"] = False
        return _private_response(payload)
