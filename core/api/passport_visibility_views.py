"""Private, owner-scoped configuration for Passport presentation audiences."""
from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from topics.models import ProfileInterest, ProfileOpenTo

from accounts.models import (
    PROFILE_VISIBILITY_FIELDS,
    ProfileVisibilityTargetKind as Target,
)
from accounts.profile_visibility import replace_profile_visibility
from accounts.profile_visibility_projection import build_profile_visibility_settings
from core.api.me_views import PersonalProjectionAPIView


class PersonalPassportVisibilityAPIView(PersonalProjectionAPIView):
    projection_code = "personal.me.passport.visibility"

    def get(self, request):
        self._guard_personal_scope(request)
        return self._response(build_profile_visibility_settings(request.user), observed_at=timezone.now())

    def put(self, request):
        self._guard_personal_scope(request, include_body=True)
        kind = request.data.get("target_kind")
        field_key = request.data.get("field_key", "")
        target_id = request.data.get("target_id")
        audiences = request.data.get("audiences")
        if kind not in Target.values or not isinstance(audiences, list):
            raise ValidationError({"target_kind": "Cible ou audiences invalides."})
        if kind == Target.FIELD:
            if target_id is not None or field_key not in PROFILE_VISIBILITY_FIELDS:
                raise ValidationError({"field_key": "Information non publiable."})
            target = {}
        elif kind == Target.INTEREST:
            if field_key or not target_id:
                raise ValidationError({"target_id": "Intérêt requis."})
            target = {"interest": get_object_or_404(
                ProfileInterest, pk=target_id, profile=request.user,
            )}
        else:
            if field_key or not target_id:
                raise ValidationError({"target_id": "Déclaration requise."})
            target = {"open_to": get_object_or_404(
                ProfileOpenTo, pk=target_id, profile=request.user,
            )}
        try:
            replace_profile_visibility(
                owner=request.user, target_kind=kind, field_key=field_key,
                audiences=audiences, **target,
            )
        except (DjangoValidationError, ValueError, TypeError) as exc:
            detail = exc.message_dict if hasattr(exc, "message_dict") else (
                exc.messages if hasattr(exc, "messages") else [str(exc)]
            )
            raise ValidationError({"audiences": detail}) from exc
        return self._response(self._payload(request.user), observed_at=timezone.now())
