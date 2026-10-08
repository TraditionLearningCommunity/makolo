from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .space_history_views import _bounded_integer
from .space_search_projection import LIMIT, MAX_LIMIT, MAX_QUERY, build_space_search
from .workspace_projection import workspace_spaces


class SpaceSearchAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, slug):
        space = workspace_spaces(request.user).filter(slug=slug).first()
        if space is None:
            raise NotFound()
        query = (request.query_params.get("q") or "").strip()
        if len(query) > MAX_QUERY:
            raise ValidationError({"q": "Recherche trop longue."})
        offset = _bounded_integer(request, "offset", default=0, minimum=0)
        limit = _bounded_integer(
            request, "limit", default=LIMIT, minimum=1, maximum=MAX_LIMIT,
        )
        payload = build_space_search(
            profile=request.user, space=space, query=query,
            responsibility_key=(request.query_params.get("responsibility") or "").strip() or None,
            offset=offset, limit=limit,
        )
        if payload is None:
            raise NotFound()
        response = Response(payload)
        response["Cache-Control"] = "private, no-store"
        return response
