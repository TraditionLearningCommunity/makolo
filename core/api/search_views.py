from django.utils import timezone
from rest_framework.exceptions import ValidationError

from core.api.history_views import _integer_param
from core.api.me_views import PersonalProjectionAPIView

from .transverse_search_projection import LIMIT, MAX_LIMIT, MAX_QUERY, build_profile_search


class PersonalSearchAPIView(PersonalProjectionAPIView):
    projection_code = "personal.search"

    def get(self, request):
        self._guard_personal_scope(request)
        query = (request.query_params.get("q") or "").strip()
        if len(query) > MAX_QUERY:
            raise ValidationError({"q": "Recherche trop longue."})
        offset = _integer_param(request, "offset", default=0, minimum=0)
        limit = _integer_param(request, "limit", default=LIMIT, minimum=1, maximum=MAX_LIMIT)
        return self._response(
            build_profile_search(profile=request.user, query=query, offset=offset, limit=limit),
            observed_at=timezone.now(),
        )
