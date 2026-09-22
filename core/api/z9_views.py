from django.utils import timezone

from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.api.projections import projection_envelope
from core.api.z9_projection import build_personal_partner_detail_data


class PersonalPartnerDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        if "profile_id" in request.query_params:
            raise ValidationError(
                {"profile_id": "Ce paramètre n'est pas accepté sur une projection personnelle."}
            )
        observed_at = timezone.now()
        data = build_personal_partner_detail_data(request.user, partner_id=pk)
        if data is None:
            from rest_framework.exceptions import NotFound

            raise NotFound()
        response = Response(
            projection_envelope(
                projection="personal.me.partner_detail",
                data=data,
                generated_at=observed_at,
            )
        )
        response["Cache-Control"] = "private, no-store"
        return response
