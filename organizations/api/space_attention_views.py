from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .space_attention_projection import (
    build_space_discover_projection,
    build_space_now_projection,
)
from .workspace_projection import workspace_spaces


class _SpaceAttentionAPIView(APIView):
    permission_classes = [IsAuthenticated]
    builder = None

    def get_space(self, request, slug):
        space = workspace_spaces(request.user).filter(slug=slug).first()
        if space is None:
            raise NotFound()
        return space

    def response(self, payload):
        response = Response(payload)
        response["Cache-Control"] = "private, no-store"
        return response


class SpaceNowAPIView(_SpaceAttentionAPIView):
    def get(self, request, slug):
        space = self.get_space(request, slug)
        payload = build_space_now_projection(
            profile=request.user,
            space=space,
            responsibility_key=(request.query_params.get("responsibility") or "").strip() or None,
        )
        if payload is None:
            raise NotFound()
        return self.response(payload)


class SpaceDiscoverAPIView(_SpaceAttentionAPIView):
    def get(self, request, slug):
        if "profile_id" in request.query_params:
            raise ValidationError({"profile_id": ["Le Profil actif est résolu par le serveur."]})
        if request.query_params.get("context") not in (None, "", "space"):
            raise ValidationError({"context": ["Contexte Space incompatible."]})
        if request.query_params.get("space") not in (None, "", slug):
            raise ValidationError({"space": ["Space incompatible avec la route."]})
        space = self.get_space(request, slug)
        try:
            payload = build_space_discover_projection(
                profile=request.user,
                space=space,
                responsibility_key=(request.query_params.get("responsibility") or "").strip() or None,
                params=request.query_params,
            )
        except DjangoValidationError as exc:
            raise ValidationError({"discovery": exc.messages}) from exc
        if payload is None:
            raise NotFound()
        return self.response(payload)
