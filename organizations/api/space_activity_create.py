"""MT3 — Native G1 creation delegated to the canonical Activity owner.

A Space member or an Activity Mandate is not an authorization to create.
The route, actor and owner are rechecked on every POST. Never cache success
for an unconfirmed mutation or create a parallel Initiative model.
"""
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from activities.forms import ActivityCreateForm
from activities.models import ActivityStatus
from activities.services import create_activity
from authorization.constants import PermissionCode
from authorization.services import can
from organizations.models import SpaceArchetype

from .workspace_projection import workspace_spaces


class SpaceG1ActivityCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, slug):
        space = workspace_spaces(request.user).filter(slug=slug).first()
        if (
            space is None
            or space.archetype not in {
                SpaceArchetype.GENERIC, SpaceArchetype.COMMUNITY,
                SpaceArchetype.CREATIVE, SpaceArchetype.MEDIA,
            }
            or not can(request.user, PermissionCode.SPACE_ACTIVITIES_MANAGE, space)
        ):
            raise NotFound()

        # The owning Space is selected by the authorized server URL; an actor
        # cannot forge it in a JSON body, and no Profile creation is offered.
        body = request.data if isinstance(request.data, dict) else {}
        if "organization" in body or "space" in body or "owner_profile" in body:
            raise ValidationError({"space": "Le propriétaire est fixé par l'Espace actif."})
        data = {
            "organization": str(space.pk),
            "title": body.get("title", ""),
            "short_description": body.get("short_description", ""),
            "description": body.get("description", ""),
            "visibility": body.get("visibility", "private"),
        }
        form = ActivityCreateForm(data=data, user=request.user)
        if not form.is_valid():
            raise ValidationError(form.errors.get_json_data())

        # The service owns subscription eligibility, Activity validation,
        # domain events and transaction boundaries; not this presentation API.
        try:
            activity = create_activity(
                space=space, created_by=request.user,
                title=form.cleaned_data["title"],
                short_description=form.cleaned_data["short_description"],
                description=form.cleaned_data["description"],
                visibility=form.cleaned_data["visibility"],
                status=ActivityStatus.DRAFT,
            )
        except DjangoValidationError as exc:
            message = (
                exc.message_dict if hasattr(exc, "message_dict")
                else exc.messages
            )
            raise ValidationError({"activity": message}) from exc

        response = Response({
            "space": {"id": str(space.pk), "slug": space.slug},
            "activity": {
                "id": str(activity.pk),
                "title": activity.title,
                "status": activity.status,
            },
        }, status=201)
        response["Cache-Control"] = "private, no-store"
        return response
