from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework.exceptions import ValidationError

from core.api.access_projection import (
    ACCESS_DEFAULT_LIMIT,
    ACCESS_MAX_LIMIT,
    ACCESS_RELATION_BENEFICIARY,
    ACCESS_RELATIONS,
    ACCESS_SEARCH_MAX_LENGTH,
    build_personal_access_credential_data,
    build_personal_accesses_data,
)
from access.selectors import accesses_for_profile
from core.api.me_views import PersonalProjectionAPIView


def _integer_param(request, name, *, default, minimum=0, maximum=None):
    raw = request.query_params.get(name)
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValidationError({name: "Ce paramètre doit être un entier."}) from exc
    if value < minimum:
        raise ValidationError(
            {name: f"Ce paramètre doit être supérieur ou égal à {minimum}."}
        )
    if maximum is not None and value > maximum:
        raise ValidationError(
            {name: f"Ce paramètre ne peut pas dépasser {maximum}."}
        )
    return value


class PersonalAccessesAPIView(PersonalProjectionAPIView):
    projection_code = "personal.accesses"

    def get(self, request):
        self._guard_personal_scope(request)
        observed_at = timezone.now()

        relationship = (
            request.query_params.get("relationship") or ACCESS_RELATION_BENEFICIARY
        ).strip()
        if relationship not in ACCESS_RELATIONS:
            raise ValidationError(
                {
                    "relationship": (
                        "Valeur attendue : beneficiary ou purchased_for_other."
                    )
                }
            )

        query = (request.query_params.get("q") or "").strip()
        if len(query) > ACCESS_SEARCH_MAX_LENGTH:
            raise ValidationError(
                {
                    "q": (
                        f"La recherche ne peut pas dépasser "
                        f"{ACCESS_SEARCH_MAX_LENGTH} caractères."
                    )
                }
            )

        limit = _integer_param(
            request,
            "limit",
            default=ACCESS_DEFAULT_LIMIT,
            minimum=1,
            maximum=ACCESS_MAX_LIMIT,
        )
        offset = _integer_param(request, "offset", default=0, minimum=0)

        data = build_personal_accesses_data(
            request.user,
            observed_at=observed_at,
            relationship=relationship,
            query=query,
            limit=limit,
            offset=offset,
        )
        return self._response(data, observed_at=observed_at)


class PersonalAccessCredentialAPIView(PersonalProjectionAPIView):
    projection_code = "personal.access.credential"

    def get(self, request, pk):
        self._guard_personal_scope(request)
        observed_at = timezone.now()
        access = get_object_or_404(
            accesses_for_profile(request.user),
            pk=pk,
        )
        data = build_personal_access_credential_data(
            profile=request.user,
            access=access,
            observed_at=observed_at,
        )
        if data is None:
            raise Http404

        response = self._response(data, observed_at=observed_at)
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response
