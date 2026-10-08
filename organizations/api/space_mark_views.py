from django.utils import timezone

from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.api.projections import projection_envelope
from core.mark_orchestration import MARK_TEXT_MAX_LENGTH
from organizations.api.workspace_projection import workspace_spaces

from .space_mark_projection import orchestrate_space_mark


_FORBIDDEN_CONTEXT_KEYS = frozenset({
    "act_as_space",
    "beneficiary_id",
    "mandate",
    "organization_actor",
    "permission",
    "profile_id",
    "role",
    "space_context",
    "space_id",
    "subject_id",
    "user_id",
})


class SpaceMarkAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def _space(self, request, slug):
        space = workspace_spaces(request.user).filter(slug=slug).first()
        if space is None:
            raise NotFound()
        return space

    def post(self, request, slug):
        space = self._space(request, slug)
        payload = request.data
        if not isinstance(payload, dict):
            raise ValidationError("Le corps de la requête doit être un objet.")

        blocked_top_level = sorted(_FORBIDDEN_CONTEXT_KEYS.intersection(payload))
        if blocked_top_level:
            raise ValidationError({
                key: "L'autorité Space est résolue par la route et le serveur."
                for key in blocked_top_level
            })

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
                    {"input": [f"Le texte est limité à {MARK_TEXT_MAX_LENGTH} caractères." ]}
                )

        context = payload.get("context") or {}
        if not isinstance(context, dict):
            raise ValidationError({"context": ["Le contexte doit être un objet."]})
        blocked = sorted(_FORBIDDEN_CONTEXT_KEYS.intersection(context))
        if blocked:
            raise ValidationError({
                key: "L'autorité Space est résolue par le serveur et ne peut pas être fournie par le client."
                for key in blocked
            })

        observed_at = timezone.now()
        result = orchestrate_space_mark(
            profile=request.user,
            space=space,
            input_kind=input_kind,
            value=value,
            context=context,
            observed_at=observed_at,
        )
        result["actor_context"] = {
            "kind": "space",
            "slug": space.slug,
        }
        result["accepted_input_kinds"] = ["text"]
        selected = context.get("selected")
        result["request_context"] = {
            "responsibility": context.get("responsibility"),
            "selected": {
                key: selected[key]
                for key in ("kind", "family")
                if isinstance(selected, dict) and selected.get(key) is not None
            }
            if isinstance(selected, dict)
            else None,
        }
        response = Response(
            projection_envelope(
                projection="space.mark",
                data=result,
                generated_at=observed_at,
                scope="space",
            )
        )
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response
