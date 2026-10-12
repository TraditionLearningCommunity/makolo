from django.shortcuts import get_object_or_404
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .space_work_projection import build_space_work_projection
from .workspace_projection import workspace_spaces


class SpaceWorkAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def _space(self, request, slug):
        space = workspace_spaces(request.user).filter(slug=slug).first()
        if space is None:
            raise NotFound()
        return space

    def get(self, request, slug):
        space = self._space(request, slug)
        try:
            offset = int(request.query_params.get("offset", "0"))
        except ValueError:
            raise ValidationError({"offset": "Décalage invalide."})
        if not 0 <= offset <= 10000:
            raise ValidationError({"offset": "Décalage hors limites."})
        payload = build_space_work_projection(
            profile=request.user,
            space=space,
            responsibility_key=(request.query_params.get("responsibility") or "").strip() or None,
            source_kind=(request.query_params.get("kind") or "").strip()[:40] or None,
            source_id=(request.query_params.get("id") or "").strip()[:80] or None,
            section_key=(request.query_params.get("section") or "").strip()[:40] or None,
            offset=offset,
        )
        if payload is None:
            raise NotFound()
        response = Response(payload)
        response["Cache-Control"] = "private, no-store"
        return response
