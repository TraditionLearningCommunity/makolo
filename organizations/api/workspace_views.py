from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from organizations.console_context import authorized_spaces, has_space_authority

from .workspace_projection import build_space_workspace


class SpaceWorkspaceListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        rows = [
            {
                "id": str(space.pk),
                "slug": space.slug,
                "name": space.name,
                "limited_to_activities": not has_space_authority(request.user, space),
                "links": {"workspace": f"/api/v1/organizations/workspaces/{space.slug}/"},
            }
            for space in authorized_spaces(request.user)[:100]
        ]
        response = Response(rows)
        response["Cache-Control"] = "private, no-store"
        return response


class SpaceWorkspaceDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, slug):
        space = authorized_spaces(request.user).filter(slug=slug).first()
        if space is None:
            raise NotFound()
        payload = build_space_workspace(request.user, space)
        if payload is None:
            raise NotFound()
        response = Response(payload)
        response["Cache-Control"] = "private, no-store"
        return response
