"""MT5 native Offer creation/editing, without a second Commerce mutation."""
from django.core.exceptions import (
    PermissionDenied as DjangoPermissionDenied,
    ValidationError as DjangoValidationError,
)
from django.http import Http404
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from organizations.models import SpaceArchetype
from organizations.space_work_g3_offer_owner import (
    SpaceOfferOwnerForm, initial_offer, offer_owner_scope, write_offer,
)

from .workspace_projection import workspace_spaces


class SpaceWorkG3OfferAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def _owner(self, request, slug, **kwargs):
        space = workspace_spaces(request.user).filter(slug=slug).first()
        if space is None or space.archetype != SpaceArchetype.COMMERCE:
            raise NotFound()
        responsibility = (
            request.query_params.get("responsibility") or "all"
        ).strip() or "all"
        try:
            activity, offer = offer_owner_scope(
                profile=request.user, space=space,
                responsibility=responsibility,
                activity_id=kwargs.get("activity_id"),
                offer_id=kwargs.get("offer_id"),
            )
        except (Http404, DjangoPermissionDenied) as exc:
            raise NotFound() from exc
        return space, responsibility, activity, offer

    @staticmethod
    def _response(space, responsibility, activity, offer, *, created=False):
        response = Response({
            "space": {"id": str(space.pk), "slug": space.slug},
            "responsibility": responsibility,
            "activity": {
                "kind": "activity", "id": str(activity.pk),
                "title": activity.title,
            },
            "offer": (
                {
                    "kind": "offer", "id": str(offer.pk), "name": offer.name,
                    "status": offer.status, "unit_price": str(offer.unit_price),
                    "currency": offer.currency,
                    "payment_mode": offer.payment_mode,
                    "min_quantity": offer.min_quantity,
                    "max_quantity": offer.max_quantity,
                    "description": offer.description,
                } if offer else None
            ),
            "options": {
                "payment_modes": list(SpaceOfferOwnerForm.base_fields[
                    "payment_mode"
                ].choices),
                "statuses": list(SpaceOfferOwnerForm.base_fields[
                    "status"
                ].choices),
            },
        }, status=201 if created else 200)
        response["Cache-Control"] = "private, no-store"
        return response

    def get(self, request, slug, **kwargs):
        space, responsibility, activity, offer = self._owner(
            request, slug, **kwargs,
        )
        return self._response(space, responsibility, activity, offer)

    def post(self, request, slug, **kwargs):
        space, responsibility, activity, offer = self._owner(
            request, slug, **kwargs,
        )
        if not isinstance(request.data, dict):
            raise ValidationError({"body": "Objet attendu."})
        if any(k in request.data for k in (
            "activity", "activity_id", "space", "organization", "owner_profile",
            "id", "source_key",
        )):
            raise ValidationError({"owner": "Ce champ ne peut pas être modifié."})
        form = SpaceOfferOwnerForm(request.data)
        if not form.is_valid():
            raise ValidationError(form.errors.get_json_data())
        try:
            saved = write_offer(
                activity=activity, offer=offer, cleaned=form.cleaned_data,
            )
        except DjangoValidationError as exc:
            reason = exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            raise ValidationError({"offer": reason}) from exc
        return self._response(
            space, responsibility, activity, saved, created=offer is None,
        )
