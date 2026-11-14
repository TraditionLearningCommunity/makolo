from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .space_pilot_projection import build_space_pilot_projection
from .space_relationships_projection import build_space_relationships_projection
from .space_us_projection import build_space_us_projection
from .space_us_authority import build_space_us_authority
from .space_us_resources_projection import build_space_us_resources_projection
from .workspace_projection import workspace_spaces


class _SpaceProjectionAPIView(APIView):
    permission_classes = [IsAuthenticated]
    builder = None

    def get(self, request, slug):
        space = workspace_spaces(request.user).filter(slug=slug).first()
        if space is None:
            raise NotFound()
        payload = self.builder(profile=request.user, space=space)
        if payload is None:
            raise NotFound()
        response = Response(payload)
        response["Cache-Control"] = "private, no-store"
        return response


class SpaceUsAPIView(_SpaceProjectionAPIView):
    builder = staticmethod(build_space_us_projection)


class SpaceUsAuthorityAPIView(_SpaceProjectionAPIView):
    builder = staticmethod(build_space_us_authority)


class SpaceUsResourcesAPIView(_SpaceProjectionAPIView):
    """Private, page-bounded Resource owner composition for a Space."""

    def get(self, request, slug):
        space = workspace_spaces(request.user).filter(slug=slug).first()
        if space is None:
            raise NotFound()
        kind = request.query_params.get("kind") or "document"
        try:
            offset = int(request.query_params.get("offset", "0"))
            payload = build_space_us_resources_projection(
                profile=request.user, space=space, kind=kind, offset=offset,
            )
        except (ValueError, TypeError) as exc:
            raise ValidationError({"resources": "Filtres de ressources invalides."}) from exc
        if payload is None:
            raise NotFound()
        response = Response(payload)
        response["Cache-Control"] = "private, no-store"
        return response


class SpaceRelationshipsAPIView(_SpaceProjectionAPIView):
    builder = staticmethod(build_space_relationships_projection)

    def get(self, request, slug):
        space = workspace_spaces(request.user).filter(slug=slug).first()
        if space is None:
            raise NotFound()
        payload = self.builder(
            profile=request.user,
            space=space,
            query=request.query_params.get('q', '')[:120],
            relation_kind=request.query_params.get('kind', '')[:40],
            relation_id=request.query_params.get('id', '')[:80],
        )
        if payload is None:
            raise NotFound()
        response = Response(payload)
        response['Cache-Control'] = 'private, no-store'
        return response


class SpacePilotAPIView(_SpaceProjectionAPIView):
    builder = staticmethod(build_space_pilot_projection)
