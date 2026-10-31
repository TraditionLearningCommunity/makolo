"""Private, owner-scoped configuration for Passport presentation audiences."""
from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from topics.models import ProfileInterest, ProfileOpenTo

from accounts.models import (
    PROFILE_VISIBILITY_FIELDS,
    ProfileVisibilityPolicy,
    ProfileVisibilityTargetKind as Target,
)
from accounts.profile_visibility import replace_profile_visibility, _collective_memberships
from groups.models import Group
from organizations.models import Organization, Team
from core.api.me_views import PersonalProjectionAPIView


class PersonalPassportVisibilityAPIView(PersonalProjectionAPIView):
    projection_code = "personal.me.passport.visibility"

    @staticmethod
    def _payload(profile):
        policies = ProfileVisibilityPolicy.objects.filter(
            owner=profile
        ).prefetch_related("audiences")
        by_key = {
            (p.target_kind, p.field_key if p.target_kind == Target.FIELD
             else str(p.interest_id if p.target_kind == Target.INTEREST else p.open_to_id)): p
            for p in policies
        }

        def setting(kind, key, *, default_public):
            policy = by_key.get((kind, str(key)))
            if policy is None:
                return {"default_public": bool(default_public), "audiences": [
                    {"kind": "public"}] if default_public else [], "configured": False}
            return {
                "default_public": bool(default_public),
                "configured": True,
                "audiences": [
                    {"kind": row.kind, **(
                        {"id": str(row.selected_profile_id),
                         "label": row.selected_profile.full_name or row.selected_profile.username}
                        if row.selected_profile_id else
                        {"id": str(row.selected_space_id)} if row.selected_space_id else
                        {"id": str(row.selected_team_id)} if row.selected_team_id else
                        {"id": str(row.selected_group_id)} if row.selected_group_id else {}
                    )}
                    for row in policy.audiences.all()
                ],
            }

        memberships = _collective_memberships(profile)
        return {
            "collectives": {
                "spaces": [
                    {"id": str(obj.pk), "label": obj.name, "kind": "selected_space"}
                    for obj in Organization.objects.filter(pk__in=memberships["spaces"]).order_by("name")
                ],
                "teams": [
                    {"id": str(obj.pk), "label": obj.name, "kind": "selected_team"}
                    for obj in Team.objects.filter(pk__in=memberships["teams"]).order_by("name")
                ],
                "groups": [
                    {"id": str(obj.pk), "label": obj.name, "kind": "selected_group"}
                    for obj in Group.objects.filter(pk__in=memberships["groups"]).order_by("name")
                ],
            },
            "audience_kinds": [
                "public", "my_collectives", "selected_space", "selected_team",
                "selected_group", "selected_profile",
            ],
            "fields": {
                key: setting(Target.FIELD, key, default_public=True)
                for key in PROFILE_VISIBILITY_FIELDS
            },
            "interests": [
                {"id": str(row.pk), "label": row.topic.label,
                 **setting(Target.INTEREST, row.pk, default_public=row.is_public)}
                for row in ProfileInterest.objects.filter(
                    profile=profile, topic__is_active=True
                ).select_related("topic").order_by("topic__label")
            ],
            "open_to": [
                {"id": str(row.pk), "label": row.get_kind_display(),
                 **setting(Target.OPEN_TO, row.pk, default_public=row.is_public)}
                for row in ProfileOpenTo.objects.filter(
                    profile=profile, is_active=True,
                ).order_by("kind")
            ],
        }

    def get(self, request):
        self._guard_personal_scope(request)
        return self._response(self._payload(request.user), observed_at=timezone.now())

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
