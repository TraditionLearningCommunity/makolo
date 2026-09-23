from django.utils import timezone

from core.api.me_views import PersonalProjectionAPIView
from core.api.personal_projections import (
    build_personal_now_projection,
    build_personal_ongoing_projection,
)


class PersonalNowAPIView(PersonalProjectionAPIView):
    projection_code = "personal.now"

    def get(self, request):
        self._guard_personal_scope(request)
        observed_at = timezone.now()
        data = build_personal_now_projection(request.user, observed_at=observed_at)
        return self._response(data, observed_at=observed_at)


class PersonalOngoingAPIView(PersonalProjectionAPIView):
    projection_code = "personal.ongoing"

    def get(self, request):
        self._guard_personal_scope(request)
        observed_at = timezone.now()
        data = build_personal_ongoing_projection(request.user, observed_at=observed_at)
        return self._response(data, observed_at=observed_at)
