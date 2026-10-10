"""Secondary Space owner depth: current authority gates all displayed owner facts.

The views contain no new business state and do not implement a generic owner.
Each concrete owner is independently queried within the selected Space scope.
"""
from urllib.parse import urlencode

from django.http import Http404
from django.urls import reverse

from activities.models import Activity, Occurrence
from authorization.constants import PermissionCode
from authorization.selectors import has_direct_space_permission
from commerce.models import CommerceOrder

from .api.space_history_projection import visible_history_activity_ids
from .space_web_views import SpaceWebMixin


class _SpaceRetrievalDetailView(SpaceWebMixin):
    template_name = "organizations/space/retrieval_owner_detail.html"
    space_page_title = "Détail"
    detail_kind = None

    def _visible_ids(self):
        ids = visible_history_activity_ids(
            profile=self.request.user,
            space=self.space,
            responsibility_key=self.selected_responsibility["key"],
        )
        if ids is None:
            raise Http404
        return ids

    def _back_url(self):
        history = self.request.GET.get("history") == "1"
        name = "organizations:space-history" if history else "organizations:space-search"
        params = {"responsibility": self.selected_responsibility["key"]}
        for key in ("q", "page", "kind", "from", "to", "selected"):
            value = (self.request.GET.get(key) or "").strip()[:120]
            if value:
                params[key] = value
        return reverse(name, kwargs={"slug": self.space.slug}) + "?" + urlencode(params)

    def _owner_data(self):
        raise NotImplementedError

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            retrieval_detail=self._owner_data(),
            retrieval_back_url=self._back_url(),
        )
        return context


class SpaceRetrievalActivityDetailView(_SpaceRetrievalDetailView):
    detail_kind = "activity"

    def _owner_data(self):
        activity = (
            Activity.objects.filter(
                pk=self.kwargs["activity_id"],
                space=self.space,
                pk__in=self._visible_ids(),
            ).first()
        )
        if activity is None:
            raise Http404
        return {
            "type": "Activité",
            "title": activity.title,
            "status": activity.get_status_display(),
            "summary": activity.short_description or None,
            "owner": "Activity",
            "time": None,
            "time_label": None,
        }


class SpaceRetrievalOccurrenceDetailView(_SpaceRetrievalDetailView):
    detail_kind = "occurrence"

    def _owner_data(self):
        occurrence = (
            Occurrence.objects.filter(
                pk=self.kwargs["occurrence_id"],
                activity__space=self.space,
                activity_id__in=self._visible_ids(),
            ).select_related("activity").first()
        )
        if occurrence is None:
            raise Http404
        return {
            "type": "Départ" if self.space.archetype == "transport_operator"
                else "Session" if self.space.archetype == "education"
                else "Séance",
            "title": occurrence.label or occurrence.activity.title,
            "status": occurrence.get_status_display(),
            "summary": occurrence.activity.title,
            "owner": "Occurrence",
            "time": occurrence.end_at or occurrence.start_at,
            "time_label": "Fin de séance" if occurrence.end_at else "Début prévu",
        }


class SpaceRetrievalOrderDetailView(_SpaceRetrievalDetailView):
    detail_kind = "commerce_order"

    def _owner_data(self):
        # Read-only Space order detail, not an arbitrary personal order lookup.
        if (
            self.selected_responsibility["key"] != "all"
            or not has_direct_space_permission(
                self.request.user, self.space, PermissionCode.ORDERS_VIEW
            )
        ):
            raise Http404
        order = (
            CommerceOrder.objects.filter(
                pk=self.kwargs["order_id"],
                payee_space=self.space,
                journey__activity_id__in=self._visible_ids(),
            ).select_related("journey__activity").first()
        )
        if order is None:
            raise Http404
        return {
            "type": "Commande",
            "title": f"Commande {order.reference}",
            "status": order.get_status_display(),
            "summary": order.journey.activity.title,
            "owner": "Commerce",
            "time": order.cancelled_at,
            "time_label": "Annulée le" if order.cancelled_at else None,
        }
