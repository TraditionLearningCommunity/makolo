"""MT4 native Programme/Prestation creation by the canonical owner services."""
from django.core.exceptions import (
    PermissionDenied as DjangoPermissionDenied,
    ValidationError as DjangoValidationError,
)
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from activities.forms import ActivityCreateForm
from organizations.models import SpaceArchetype
from services.models import ServiceKind

from organizations.space_work_g2_creation import (
    create_g2_owner, g2_creation_available,
)
from .workspace_projection import workspace_spaces


class SpaceWorkG2CreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, slug):
        space = workspace_spaces(request.user).filter(slug=slug).first()
        if space is None or not g2_creation_available(request.user, space):
            raise NotFound()
        if not isinstance(request.data, dict):
            raise ValidationError({"body": "Objet attendu."})
        data = request.data
        if any(k in data for k in ("space", "organization", "owner_profile", "status")):
            raise ValidationError({"owner": "Ces informations ne peuvent pas être définies ici."})
        form = ActivityCreateForm(
            data={
                "organization": str(space.pk),
                "title": data.get("title", ""),
                "short_description": data.get("short_description", ""),
                "description": data.get("description", ""),
                "visibility": data.get("visibility", "private"),
            },
            user=request.user,
        )
        if not form.is_valid():
            raise ValidationError(form.errors.get_json_data())
        service_kind = data.get("service_kind")
        if space.archetype == SpaceArchetype.SERVICE_PROVIDER:
            if service_kind not in {kind for kind, _ in ServiceKind.choices}:
                raise ValidationError({"service_kind": "Type de prestation invalide."})
        elif service_kind is not None:
            raise ValidationError({"service_kind": "Les Programmes ne sont pas des Services."})
        try:
            activity, service = create_g2_owner(
                actor=request.user, space=space,
                title=form.cleaned_data["title"],
                short_description=form.cleaned_data["short_description"],
                description=form.cleaned_data["description"],
                visibility=form.cleaned_data["visibility"],
                service_kind=service_kind,
            )
        except DjangoPermissionDenied as exc:
            raise NotFound() from exc
        except DjangoValidationError as exc:
            value = exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            raise ValidationError({"creation": value}) from exc
        response = Response({
            "space": {"id": str(space.pk), "slug": space.slug},
            "activity": {
                "id": str(activity.pk), "title": activity.title,
                "status": activity.status,
            },
            "service": (
                {"id": str(service.pk), "kind": service.service_kind}
                if service is not None else None
            ),
        }, status=201)
        response["Cache-Control"] = "private, no-store"
        return response
