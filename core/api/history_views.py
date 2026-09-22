from django.utils import timezone

from rest_framework.exceptions import ValidationError

from core.api.history_projection import (
    HISTORY_DEFAULT_LIMIT,
    HISTORY_FILTER_ALL,
    HISTORY_FILTERS,
    HISTORY_MAX_LIMIT,
    HISTORY_SEARCH_MAX_LENGTH,
    build_personal_history_data,
)
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


class PersonalHistoryAPIView(PersonalProjectionAPIView):
    projection_code = "personal.history"

    def get(self, request):
        self._guard_personal_scope(request)
        observed_at = timezone.now()

        history_filter = (
            request.query_params.get("type") or HISTORY_FILTER_ALL
        ).strip().lower()
        if history_filter not in HISTORY_FILTERS:
            raise ValidationError(
                {"type": "Valeur attendue : all, accesses ou journeys."}
            )

        query = (request.query_params.get("q") or "").strip()
        if len(query) > HISTORY_SEARCH_MAX_LENGTH:
            raise ValidationError(
                {
                    "q": (
                        f"La recherche ne peut pas dépasser "
                        f"{HISTORY_SEARCH_MAX_LENGTH} caractères."
                    )
                }
            )

        limit = _integer_param(
            request,
            "limit",
            default=HISTORY_DEFAULT_LIMIT,
            minimum=1,
            maximum=HISTORY_MAX_LIMIT,
        )
        offset = _integer_param(request, "offset", default=0, minimum=0)

        data = build_personal_history_data(
            request.user,
            observed_at=observed_at,
            history_filter=history_filter,
            query=query,
            limit=limit,
            offset=offset,
        )
        response = self._response(data, observed_at=observed_at)
        response["Cache-Control"] = "private, no-store"
        return response
