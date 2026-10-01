from django.shortcuts import get_object_or_404
from rest_framework.exceptions import NotFound
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
        payload = build_space_work_projection(
            profile=request.user,
            space=space,
            responsibility_key=(request.query_params.get("responsibility") or "").strip() or None,
        )
        if payload is None:
            raise NotFound()
        response = Response(payload)
        response["Cache-Control"] = "private, no-store"
        return response
