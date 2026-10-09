from uuid import UUID

from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .space_history_projection import (
    DEFAULT_LIMIT, MAX_LIMIT, MAX_QUERY_LENGTH, build_space_history_projection,
)
from .workspace_projection import workspace_spaces


def _bounded_integer(request, name, *, default, minimum, maximum=None):
    raw = request.query_params.get(name)
    if raw is None or raw == "":
        return default
    try:
        result = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValidationError({name: "Un entier est attendu."}) from exc
    if result < minimum or (maximum is not None and result > maximum):
        raise ValidationError({name: "Valeur hors limites."})
    return result


class SpaceHistoryAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, slug):
        space = workspace_spaces(request.user).filter(slug=slug).first()
        if space is None:
            raise NotFound()
        query = (request.query_params.get("q") or "").strip()
        if len(query) > MAX_QUERY_LENGTH:
            raise ValidationError({"q": "Recherche trop longue."})
        offset = _bounded_integer(request, "offset", default=0, minimum=0)
        limit = _bounded_integer(
            request, "limit", default=DEFAULT_LIMIT, minimum=1, maximum=MAX_LIMIT,
        )
        responsibility = (request.query_params.get("responsibility") or "").strip() or None
        if responsibility and responsibility != "all":
            if not responsibility.startswith("mandate:"):
                raise NotFound()
            try:
                UUID(responsibility.removeprefix("mandate:"))
            except (ValueError, TypeError):
                raise NotFound() from None
        payload = build_space_history_projection(
            profile=request.user, space=space, query=query,
            responsibility_key=responsibility,
            offset=offset, limit=limit,
        )
        if payload is None:
            raise NotFound()
        response = Response(payload)
        response["Cache-Control"] = "private, no-store"
        return response
