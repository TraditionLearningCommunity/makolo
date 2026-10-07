from django.core import signing
from django.utils import timezone

from rest_framework.exceptions import ValidationError

from core.api.me_views import PersonalProjectionAPIView
from core.api.personal_projections import (
    build_personal_ongoing_projection,
    build_personal_now_projection,
    ongoing_continuation_offset,
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
        try:
            offset = ongoing_continuation_offset(
                request.query_params.get("continuation")
            )
        except (signing.BadSignature, KeyError, TypeError, ValueError) as exc:
            raise ValidationError(
                {"continuation": "Ce token de continuation est invalide."}
            ) from exc
        data = build_personal_ongoing_projection(
            request.user,
            observed_at=observed_at,
            continuation_offset=offset,
        )
        return self._response(data, observed_at=observed_at)
