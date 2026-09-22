from django.core.exceptions import ValidationError

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.mark_orchestration import (
    MARK_TEXT_MAX_LENGTH,
    orchestrate_mark,
    public_mark_result,
)

from .projections import projection_envelope


class PersonalMarkAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        payload = request.data
        if not isinstance(payload, dict):
            raise ValidationError("Le corps de la requête doit être un objet.")

        mark_input = payload.get("input")
        if not isinstance(mark_input, dict):
            raise ValidationError({"input": ["Une entrée Mark structurée est requise."]})

        input_kind = str(mark_input.get("kind") or "").strip()
        value = mark_input.get("value")
        if not input_kind:
            raise ValidationError({"input": ["Le type d'entrée est requis."]})
        if input_kind == "text":
            value = str(value or "").strip()
            if not value:
                raise ValidationError({"input": ["Le texte ne peut pas être vide."]})
            if len(value) > MARK_TEXT_MAX_LENGTH:
                raise ValidationError(
                    {"input": [f"Le texte est limité à {MARK_TEXT_MAX_LENGTH} caractères."]}
                )

        context = payload.get("context") or {}
        if not isinstance(context, dict):
            raise ValidationError({"context": ["Le contexte doit être un objet."]})

        result = orchestrate_mark(
            profile=request.user,
            input_kind=input_kind,
            value=value,
            context=context,
        )
        return Response(
            projection_envelope(
                projection="personal.mark",
                data=public_mark_result(result),
            )
        )
