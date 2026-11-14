"""MT5 Web N3 Transport operator actions through canonical domain services."""
from urllib.parse import urlencode

from django.contrib import messages
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import TemplateView

from organizations.models import SpaceArchetype
from transport.models import TransportDeparture, Vehicle

from .api.space_work_g3_transport_operations import (
    perform_transport_departure_action, transport_departure_actions,
    transport_departure_owner,
)
from .space_web_views import SpaceWebMixin
from .space_work_g3_web import g3_depth_url


class SpaceWorkG3DepartureOperationsView(SpaceWebMixin):
    template_name = "organizations/space/work_g3_departure_operations.html"
    space_nav_key = "work"
    space_page_title = "Exploiter le départ"

    def _owner(self):
        if self.space.archetype != SpaceArchetype.TRANSPORT_OPERATOR:
            raise Http404
        return transport_departure_owner(
            profile=self.request.user,
            space=self.space,
            responsibility=self.selected_responsibility["key"],
            departure_id=self.kwargs["departure_id"],
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        departure = self._owner()
        responsibility = self.selected_responsibility["key"]
        action_flags = transport_departure_actions(
            self.request.user, self.space, responsibility, departure,
        )
        context.update({
            "mt5_departure": departure,
            "mt5_actions": action_flags,
            "mt5_vehicles": (
                Vehicle.objects.filter(space=self.space, active=True)
                .order_by("label", "pk")
                if action_flags["can_assign_vehicle"] else Vehicle.objects.none()
            ),
            "mt5_back_url": g3_depth_url(
                self.space, "occurrence", departure.occurrence_id,
                responsibility=responsibility, origin_section="active",
            ),
        })
        return context

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        departure = self._owner()
        departure = (
            TransportDeparture.objects.select_for_update()
            .select_related("occurrence__activity")
            .get(pk=departure.pk)
        )
        form_data = {
            "action": request.POST.get("action"),
            "vehicle": request.POST.get("vehicle"),
            "timezone": request.POST.get("timezone"),
            "start_at": request.POST.get("start_at"),
            "end_at": request.POST.get("end_at"),
            "confirmed": request.POST.get("confirmed") == "yes",
        }
        try:
            perform_transport_departure_action(
                departure=departure, actor=request.user, space=self.space,
                responsibility=self.selected_responsibility["key"],
                data=form_data,
            )
        except DjangoValidationError as exc:
            message = (
                "; ".join(exc.messages)
                if hasattr(exc, "messages") else str(exc)
            )
            messages.error(request, message)
        except Exception as exc:
            # Owner validation from the API raises the DRF ValidationError;
            # catch that only, and preserve all unexpected errors for diagnosis.
            from rest_framework.exceptions import (
                NotFound as OwnerNotFound,
                ValidationError as OwnerValidationError,
            )
            if isinstance(exc, OwnerNotFound):
                raise Http404 from exc
            if not isinstance(exc, OwnerValidationError):
                raise
            messages.error(request, str(exc.detail))
        else:
            messages.success(request, "Le propriétaire Transport a confirmé l'action.")
        return redirect(
            reverse(
                "organizations:space-work-g3-departure-operations",
                kwargs={
                    "slug": self.space.slug, "departure_id": departure.pk,
                },
            ) + "?" + urlencode({
                "responsibility": self.selected_responsibility["key"],
            })
        )
