"""G1 / MT3: owner-backed Métier depth for Activités and Initiatives.

This is presentation and navigation, not an Activity, Journey or Occurrence
owner. The current Space Work selection gates every N2 entry.
"""
from __future__ import annotations

from urllib.parse import urlencode

from django.core.paginator import Paginator
from django.http import Http404
from django.urls import reverse

from funding.models import FundingDetails
from funding.services import can_manage_funding
from journeys.models import Journey

from activities.models import Activity, Occurrence
from authorization.constants import PermissionCode
from authorization.services import can
from organizations.models import SpaceArchetype

from .api.space_work_projection import build_space_work_projection
from .space_web_views import SpaceWebMixin


_G1_ARCHETYPES = {SpaceArchetype.GENERIC, SpaceArchetype.COMMUNITY}
_G1_KINDS = {"activity", "occurrence", "journey"}
_ROOT_SECTIONS = {
    "activities", "preparation", "upcoming", "active", "blocked",
    "completed", "requests",
}
_PAGE_SIZE = 12


def _work_depth_url(space, kind, identity, *, responsibility, origin_section,
                    origin=None, page=None):
    url = reverse(
        "organizations:space-work-depth",
        kwargs={"slug": space.slug, "kind": kind, "owner_id": identity},
    )
    params = {"responsibility": responsibility, "from": origin_section}
    if origin == "activity":
        params["origin"] = "activity"
    if page is not None:
        params["page"] = page
    return f"{url}?{urlencode(params)}"


class SpaceWorkG1DepthView(SpaceWebMixin):
    """N2: real Activity, Occurrence or Journey, in one current Space scope."""

    template_name = "organizations/space/work_depth.html"
    space_nav_key = "work"
    space_page_title = "Métier"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.space.archetype not in _G1_ARCHETYPES:
            raise Http404

        kind = self.kwargs["kind"]
        identity = self.kwargs["owner_id"]
        if kind not in _G1_KINDS:
            raise Http404
        responsibility = self.selected_responsibility["key"]
        projection = build_space_work_projection(
            profile=self.request.user, space=self.space,
            responsibility_key=responsibility,
            source_kind=kind, source_id=str(identity),
        )
        selection = (projection or {}).get("selection")
        if not selection or selection.get("source") != {
            "kind": kind, "id": str(identity),
        }:
            raise Http404

        origin_section = self.request.GET.get("from", "activities")
        if origin_section not in _ROOT_SECTIONS:
            origin_section = "activities"
        work_url = self._space_nav_url("organizations:space-work")
        back_url = f"{work_url}#work-{origin_section}"
        root_back_label = "Retour aux initiatives" if (
            self.space.archetype == SpaceArchetype.COMMUNITY
        ) else "Retour aux activités"
        activity_id = (
            identity if kind == "activity"
            else (selection.get("context") or {}).get("activity", {}).get("id")
        )
        activity = (
            Activity.objects.filter(pk=activity_id, space=self.space).first()
            if activity_id else None
        )
        if activity is None:
            # Never render a detached Journey/Occurrence or a foreign Activity.
            raise Http404

        actions = []
        parent_url = None
        if kind == "activity":
            activity_can_manage = (
                "manage" in selection.get("capabilities", ())
                and can(self.request.user, PermissionCode.ACTIVITY_MANAGE, activity=activity)
            )
            if activity_can_manage:
                # Both owner views perform their own permission checks.
                actions.extend([
                    {
                        "label": "Gérer l’activité" if (
                            self.space.archetype == SpaceArchetype.GENERIC
                        ) else "Gérer l’initiative",
                        "url": reverse(
                            "organizations:console-activity-detail",
                            kwargs={"slug": self.space.slug, "activity_id": activity.pk},
                        ),
                    },
                    {
                        "label": "Gérer les ressources",
                        "url": reverse(
                            "preparation:manage", kwargs={"activity_id": activity.pk},
                        ),
                    },
                ])
            if self.space.archetype == SpaceArchetype.COMMUNITY:
                # Funding is a real optional Activity vertical; it is never
                # inferred from the Espace being a community.
                funding = FundingDetails.objects.filter(activity=activity).first()
                if funding is not None and can_manage_funding(self.request.user, funding):
                    actions.append({
                        "label": "Gérer le financement",
                        "url": reverse("funding:manage", kwargs={"pk": funding.pk}),
                    })
        else:
            # The parent is itself revalidated through the same owner selector.
            parent_projection = build_space_work_projection(
                profile=self.request.user, space=self.space,
                responsibility_key=responsibility,
                source_kind="activity", source_id=str(activity.pk),
            )
            if (parent_projection or {}).get("selection"):
                origin_page = self.request.GET.get("page")
                if not (origin_page and len(origin_page) <= 5 and origin_page.isdecimal()
                        and 1 <= int(origin_page) <= 10000):
                    origin_page = None
                parent_url = _work_depth_url(
                    self.space, "activity", activity.pk,
                    responsibility=responsibility, origin_section=origin_section,
                    page=origin_page,
                )
                if self.request.GET.get("origin") == "activity":
                    back_url = parent_url
                    root_back_label = "Retour à l’initiative" if (
                        self.space.archetype == SpaceArchetype.COMMUNITY
                    ) else "Retour à l’activité"

        if kind == "occurrence" and "open_day_of" in selection.get("capabilities", ()):
            if (selection.get("links") or {}).get("day_of"):
                actions.append({
                    "label": "Ouvrir Jour J",
                    "url": reverse(
                        "organizations:space-occurrence-day-of",
                        kwargs={"slug": self.space.slug, "occurrence_id": identity},
                    ) + "?" + urlencode({"responsibility": responsibility}),
                })

        if kind == "activity":
            # A relation is shown only under the currently permitted Activity.
            # No beneficiary, registration, QR or private resource is projected.
            occurrences = (
                Occurrence.objects.filter(activity=activity)
                .select_related("activity")
                .order_by("start_date", "start_time", "pk")
            )
            requested_page = self.request.GET.get("page", "1")
            page = Paginator(occurrences, _PAGE_SIZE).get_page(requested_page)
            next_page_url = (
                _work_depth_url(
                    self.space, kind, identity,
                    responsibility=responsibility, origin_section=origin_section,
                    page=page.next_page_number(),
                ) if page.has_next() else None
            )
            previous_page_url = (
                _work_depth_url(
                    self.space, kind, identity,
                    responsibility=responsibility, origin_section=origin_section,
                    page=page.previous_page_number(),
                ) if page.has_previous() else None
            )
            related = [{
                "identity": f"occurrence:{occurrence.pk}",
                "title": occurrence.label or activity.title,
                "status": occurrence.get_status_display(),
                "date": occurrence.start_date,
                "time": occurrence.start_time,
                "url": _work_depth_url(
                    self.space, "occurrence", occurrence.pk,
                    responsibility=responsibility, origin_section=origin_section,
                    origin="activity", page=page.number if page.number > 1 else None,
                ),
            } for occurrence in page.object_list]
        else:
            related = []
            next_page_url = previous_page_url = None

        owner_status = selection.get("state")
        if kind == "activity":
            owner_status = activity.get_status_display()
        elif kind == "occurrence":
            occurrence = Occurrence.objects.filter(
                pk=identity, activity=activity,
            ).first()
            if occurrence is None:
                raise Http404
            owner_status = occurrence.get_status_display()
        elif kind == "journey":
            journey = Journey.objects.filter(pk=identity, activity=activity).first()
            if journey is None:
                raise Http404
            owner_status = journey.get_status_display()

        context.update({
            "work_depth": {
                "kind": kind,
                "identity": selection["entry_identity"],
                "title": selection["title"],
                "summary": selection.get("summary"),
                "status": owner_status,
                "context": selection.get("context") or {},
                "timing": selection.get("timing") or {},
                "is_initiative": self.space.archetype == SpaceArchetype.COMMUNITY,
                "is_activity": kind == "activity",
                "is_occurrence": kind == "occurrence",
                "is_journey": kind == "journey",
                "actions": actions,
                "related": related,
                "next_page_url": next_page_url,
                "previous_page_url": previous_page_url,
                "parent_url": parent_url,
                "back_url": back_url,
                "back_label": root_back_label,
            },
        })
        return context
