"""MT5 owner-backed Web form for Commerce Offer."""
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from django.shortcuts import redirect

from organizations.models import SpaceArchetype

from .space_web_views import SpaceWebMixin
from .space_work_g3_offer_owner import (
    SpaceOfferOwnerForm, initial_offer, offer_owner_scope, write_offer,
)
from .space_work_g3_web import g3_depth_url


class SpaceWorkG3OfferView(SpaceWebMixin):
    template_name = "organizations/space/work_g3_offer_form.html"
    space_nav_key = "work"
    space_page_title = "Offre"

    def _owner(self):
        if self.space.archetype != SpaceArchetype.COMMERCE:
            raise Http404
        return offer_owner_scope(
            profile=self.request.user, space=self.space,
            responsibility=self.selected_responsibility["key"],
            activity_id=self.kwargs.get("activity_id"),
            offer_id=self.kwargs.get("offer_id"),
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        activity, offer = self._owner()
        responsibility = self.selected_responsibility["key"]
        back_url = g3_depth_url(
            self.space, "offer", offer.pk,
            responsibility=responsibility, origin_section="offers",
        ) if offer else g3_depth_url(
            self.space, "activity", activity.pk,
            responsibility=responsibility, origin_section="activities",
        )
        context.update({
            "offer_form": kwargs.get("offer_form") or SpaceOfferOwnerForm(
                initial=initial_offer(offer),
            ),
            "offer_activity": activity,
            "offer_owner": offer,
            "offer_back_url": back_url,
            "offer_title": "Modifier l’offre" if offer else "Nouvelle offre",
        })
        return context

    def post(self, request, *args, **kwargs):
        activity, offer = self._owner()
        if any(k in request.POST for k in (
            "activity", "activity_id", "space", "organization",
            "owner_profile", "source_key",
        )):
            raise PermissionDenied("Le propriétaire de cette Offre ne se déplace pas.")
        form = SpaceOfferOwnerForm(request.POST)
        if form.is_valid():
            try:
                saved = write_offer(
                    activity=activity, offer=offer, cleaned=form.cleaned_data,
                )
            except (ValidationError, PermissionDenied) as exc:
                form.add_error(
                    None,
                    "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc),
                )
            else:
                messages.success(
                    request, "Offre créée en brouillon."
                    if offer is None else "Offre mise à jour.",
                )
                return redirect(g3_depth_url(
                    self.space, "offer", saved.pk,
                    responsibility=self.selected_responsibility["key"],
                    origin_section="offers",
                ))
        return self.render_to_response(self.get_context_data(offer_form=form))
