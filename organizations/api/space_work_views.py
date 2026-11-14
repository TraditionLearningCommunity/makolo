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
        try:
            related_offset = int(request.query_params.get("related_offset", "0"))
        except ValueError:
            raise ValidationError({"related_offset": "Décalage invalide."})
        if not 0 <= related_offset <= 10000:
            raise ValidationError({"related_offset": "Décalage hors limites."})
        if related_offset and (
            request.query_params.get("kind") != "activity"
            or not request.query_params.get("id")
        ):
            raise ValidationError({
                "related_offset": "Une activité doit être sélectionnée.",
            })
        try:
            related_work_offset = int(request.query_params.get("related_work_offset", "0"))
        except (ValueError, TypeError):
            raise ValidationError({"related_work_offset": "Décalage invalide."})
        if not 0 <= related_work_offset <= 10000:
            raise ValidationError({"related_work_offset": "Décalage hors limites."})
        if related_work_offset and (
            request.query_params.get("kind") != "activity"
            or not request.query_params.get("id")
        ):
            raise ValidationError({
                "related_work_offset": "Une activité doit être sélectionnée.",
            })
        g3_offsets = {}
        for key in ("g3_offset", "g3_secondary_offset"):
            try:
                value = int(request.query_params.get(key, "0"))
            except (ValueError, TypeError):
                raise ValidationError({key: "Décalage invalide."})
            if not 0 <= value <= 10000:
                raise ValidationError({key: "Décalage hors limites."})
            g3_offsets[key] = value
        if any(g3_offsets.values()) and (
            request.query_params.get("kind") not in {
                "activity", "transport_route", "vehicle", "commerce_order"
            }
            or not request.query_params.get("id")
        ):
            raise ValidationError({"g3_offset": "Choisissez un propriétaire."})
        if g3_offsets["g3_secondary_offset"] and (
            request.query_params.get("kind") != "transport_route"
        ):
            raise ValidationError({
                "g3_secondary_offset": "Réservé aux relations Route.",
            })
        payload = build_space_work_projection(
            profile=request.user,
            space=space,
            responsibility_key=(request.query_params.get("responsibility") or "").strip() or None,
            source_kind=(request.query_params.get("kind") or "").strip()[:40] or None,
            source_id=(request.query_params.get("id") or "").strip()[:80] or None,
            section_key=(request.query_params.get("section") or "").strip()[:40] or None,
            offset=offset, related_offset=related_offset,
            related_work_offset=related_work_offset,
            **g3_offsets,
        )
        if payload is None:
            raise NotFound()
        response = Response(payload)
        response["Cache-Control"] = "private, no-store"
        return response
