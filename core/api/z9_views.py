from django.utils import timezone

from rest_framework.exceptions import NotFound

from core.api.me_views import PersonalProjectionAPIView
from core.api.z9_projection import build_personal_partner_detail_data


class PersonalPartnerDetailAPIView(PersonalProjectionAPIView):
    projection_code = "personal.me.partner_detail"

    def get(self, request, pk):
        self._guard_personal_scope(request)
        observed_at = timezone.now()
        data = build_personal_partner_detail_data(request.user, partner_id=pk)
        if data is None:
            raise NotFound()
        return self._response(data, observed_at=observed_at)
