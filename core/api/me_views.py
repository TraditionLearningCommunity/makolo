from django.utils import timezone

from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.api.me_projection import (
    PASSPORT_COMPLETE,
    build_personal_collectives_data,
    build_personal_considerations_data,
    build_personal_me_data,
    build_personal_partners_data,
    build_personal_passport_data,
    build_personal_resources_data,
)
from core.api.projections import projection_envelope


class PersonalProjectionAPIView(APIView):
    """Shared guard for private Mature projections rooted in request.user."""

    permission_classes = [IsAuthenticated]
    projection_code = ""

    def _guard_personal_scope(self, request):
        if "profile_id" in request.query_params:
            raise ValidationError(
                {"profile_id": "Ce paramètre n'est pas accepté sur une projection personnelle."}
            )

    def _response(self, data, *, observed_at):
        return Response(
            projection_envelope(
                projection=self.projection_code,
                data=data,
                generated_at=observed_at,
            )
        )


class PersonalMeAPIView(PersonalProjectionAPIView):
    """Private Mature projection for the authenticated person's Moi surface."""

    projection_code = "personal.me"

    def get(self, request):
        self._guard_personal_scope(request)
        observed_at = timezone.now()
        data = build_personal_me_data(profile=request.user, request=request)
        return self._response(data, observed_at=observed_at)


class PersonalConsiderationsAPIView(PersonalProjectionAPIView):
    projection_code = "personal.me.considerations"

    def get(self, request):
        self._guard_personal_scope(request)
        observed_at = timezone.now()
        return self._response(
            build_personal_considerations_data(request.user),
            observed_at=observed_at,
        )


class PersonalCollectivesAPIView(PersonalProjectionAPIView):
    projection_code = "personal.me.collectives"

    def get(self, request):
        self._guard_personal_scope(request)
        observed_at = timezone.now()
        return self._response(
            build_personal_collectives_data(request.user),
            observed_at=observed_at,
        )


class PersonalPassportAPIView(PersonalProjectionAPIView):
    projection_code = "personal.me.passport"

    def get(self, request):
        self._guard_personal_scope(request)
        observed_at = timezone.now()
        variant = (request.query_params.get("variant") or PASSPORT_COMPLETE).strip()
        try:
            data = build_personal_passport_data(
                request.user,
                variant=variant,
                topic_codes=request.query_params.getlist("topic"),
                selected_activity_ids=request.query_params.getlist("activity"),
                selected_proof_ids=request.query_params.getlist("proof"),
                selected_credential_ids=request.query_params.getlist("credential"),
                selected_sections=request.query_params.getlist("include"),
            )
        except ValueError as exc:
            raise ValidationError({"variant": str(exc)}) from exc
        return self._response(data, observed_at=observed_at)


class PersonalResourcesAPIView(PersonalProjectionAPIView):
    projection_code = "personal.me.resources"

    def get(self, request):
        self._guard_personal_scope(request)
        observed_at = timezone.now()
        return self._response(
            build_personal_resources_data(request.user),
            observed_at=observed_at,
        )


class PersonalPartnersAPIView(PersonalProjectionAPIView):
    projection_code = "personal.me.partners"

    def get(self, request):
        self._guard_personal_scope(request)
        observed_at = timezone.now()
        return self._response(
            build_personal_partners_data(request.user),
            observed_at=observed_at,
        )
