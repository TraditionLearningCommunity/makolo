"""MT5: contextual Commerce/Transport N2, never an alternate business owner."""
from urllib.parse import urlencode

from django.http import Http404
from django.urls import reverse

from activities.models import Activity
from authorization.constants import PermissionCode
from authorization.selectors import has_direct_space_permission
from authorization.services import can
from organizations.models import SpaceArchetype

from .api.space_work_projection import build_space_work_projection
from .space_web_views import SpaceWebMixin
from .space_work_navigation import restore_work_origin


G3_KINDS = {
    SpaceArchetype.COMMERCE: {"offer", "commerce_order", "activity"},
    SpaceArchetype.TRANSPORT_OPERATOR: {
        "activity", "occurrence", "transport_route", "vehicle",
    },
}
ROOT_SECTIONS = {
    "active", "upcoming", "preparation", "blocked", "completed",
    "activities", "offers", "routes", "vehicles",
}
PAGE_SIZE = 12


def g3_depth_url(space, kind, identity, *, responsibility, origin_section,
                 page=None, secondary_page=None, origin=None):
    url = reverse(
        "organizations:space-work-depth-g3",
        kwargs={"slug": space.slug, "kind": kind, "owner_id": identity},
    )
    params = {"responsibility": responsibility, "from": origin_section}
    if page is not None:
        params["page"] = page
    if secondary_page is not None:
        params["page2"] = secondary_page
    if origin == "parent":
        params["origin"] = origin
    return url + "?" + urlencode(params)


def _offset(raw):
    raw = (raw or "1").strip()
    if not raw.isdecimal() or len(raw) > 4 or not 1 <= int(raw) <= 834:
        raise Http404
    return (int(raw) - 1) * PAGE_SIZE


class SpaceWorkG3DepthView(SpaceWebMixin):
    template_name = "organizations/space/work_g3_depth.html"
    space_nav_key = "work"
    space_page_title = "Métier"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        kind = self.kwargs["kind"]
        owner_id = str(self.kwargs["owner_id"])
        if kind not in G3_KINDS.get(self.space.archetype, set()):
            raise Http404

        responsibility = self.selected_responsibility["key"]
        origin_section = self.request.GET.get("from", "activities")
        if origin_section not in ROOT_SECTIONS:
            origin_section = "activities"
        offset, offset2 = _offset(self.request.GET.get("page")), _offset(
            self.request.GET.get("page2")
        )
        projection = build_space_work_projection(
            profile=self.request.user, space=self.space,
            responsibility_key=responsibility,
            source_kind=kind, source_id=owner_id,
            g3_offset=offset, g3_secondary_offset=offset2,
        )
        selection = (projection or {}).get("selection")
        if not selection or selection.get("source") != {
            "kind": kind, "id": owner_id,
        }:
            raise Http404
        detail = selection.get("owner_depth") or {}
        if not detail and kind != "activity":
            raise Http404
        is_commerce = self.space.archetype == SpaceArchetype.COMMERCE
        root = self._space_nav_url("organizations:space-work")
        back_url = root + "#work-" + origin_section
        back_label = "Retour au Commerce" if is_commerce else "Retour au Transport"
        actions = []
        linked_activity = (selection.get("context") or {}).get("activity") or {}
        activity_id = (
            owner_id if kind == "activity"
            else linked_activity.get("id")
        )
        activity = (
            Activity.objects.filter(pk=activity_id, space=self.space).first()
            if activity_id else None
        )
        if kind == "offer":
            if activity and can(
                self.request.user, PermissionCode.ACTIVITY_COMMERCE_MANAGE,
                activity=activity,
            ):
                actions.append({
                    "label": "Modifier cette offre",
                    "url": reverse(
                        "organizations:space-work-g3-offer-edit",
                        kwargs={
                            "slug": self.space.slug, "offer_id": owner_id,
                        },
                    ) + "?" + urlencode({"responsibility": responsibility}),
                })
        elif kind == "activity" and is_commerce and activity:
            if can(
                self.request.user, PermissionCode.ACTIVITY_COMMERCE_MANAGE,
                activity=activity,
            ):
                actions.append({
                    "label": "Créer une offre",
                    "url": reverse(
                        "organizations:space-work-g3-offer-create",
                        kwargs={
                            "slug": self.space.slug, "activity_id": activity.pk,
                        },
                    ) + "?" + urlencode({"responsibility": responsibility}),
                })
        elif kind == "commerce_order":
            if (
                responsibility == "all" and
                has_direct_space_permission(
                    self.request.user, self.space, PermissionCode.ORDERS_VIEW,
                )
            ):
                actions.append({
                    "label": "Consulter les commandes",
                    "url": reverse(
                        "organizations:console-orders",
                        kwargs={"slug": self.space.slug},
                    ),
                })
        elif kind == "occurrence" and detail.get("kind") == "transport_departure":
            if activity and detail.get("facts", {}).get("can_manage_operations") and can(
                self.request.user,
                PermissionCode.ACTIVITY_OPERATIONS_MANAGE,
                activity=activity,
            ):
                actions.append({
                    "label": "Exploiter ce départ",
                    "url": reverse(
                        "organizations:space-work-g3-departure-operations",
                        kwargs={
                            "slug": self.space.slug,
                            "departure_id": detail["facts"]["departure_id"],
                        },
                    ) + "?" + urlencode({"responsibility": responsibility}),
                })
            elif activity and detail.get("facts", {}).get("operations_visible") and can(
                self.request.user,
                PermissionCode.ACTIVITY_OPERATIONS_VIEW,
                activity=activity,
            ):
                # Read-only operations remain owned by the existing Console.
                actions.append({
                    "label": "Consulter les opérations",
                    "url": reverse(
                        "organizations:console-transport-departure-detail",
                        kwargs={
                            "slug": self.space.slug,
                            "departure_id": detail["facts"]["departure_id"],
                        },
                    ),
                })
            if (
                "open_day_of" in selection.get("capabilities", ())
                and (selection.get("links") or {}).get("day_of")
            ):
                actions.append({
                    "label": "Ouvrir Jour J",
                    "url": reverse(
                        "organizations:space-occurrence-day-of",
                        kwargs={"slug": self.space.slug, "occurrence_id": owner_id},
                    ) + "?" + urlencode({"responsibility": responsibility}),
                })
        elif kind in {"transport_route", "vehicle"}:
            if responsibility == "all" and has_direct_space_permission(
                self.request.user, self.space, PermissionCode.SPACE_ACTIVITIES_VIEW,
            ):
                actions.append({
                    "label": "Gérer le transport",
                    "url": reverse(
                        "organizations:console-transport",
                        kwargs={"slug": self.space.slug},
                    ),
                })
        elif kind == "activity" and activity and can(
            self.request.user, PermissionCode.ACTIVITY_MANAGE,
            activity=activity,
        ):
            actions.append({
                "label": "Préparer les ressources",
                "url": reverse(
                    "preparation:manage",
                    kwargs={"activity_id": activity.pk},
                ),
            })

        def linked_collection(key, *, other=False):
            raw = detail.get(key) or {}
            rows = []
            for item in raw.get("items", ()):
                source = item.get("source") or {}
                if source.get("kind") in G3_KINDS[self.space.archetype]:
                    route = g3_depth_url(
                        self.space, source["kind"], source["id"],
                        responsibility=responsibility,
                        origin_section=origin_section,
                        origin="parent",
                        page=(offset // PAGE_SIZE + 1) if offset else None,
                        secondary_page=(offset2 // PAGE_SIZE + 1) if offset2 else None,
                    ) if item.get("openable", True) else None
                else:
                    route = None
                rows.append({**item, "url": route})
            page = offset2 if other else offset
            pg = page // PAGE_SIZE + 1
            def url(n):
                return g3_depth_url(
                    self.space, kind, owner_id,
                    responsibility=responsibility,
                    origin_section=origin_section,
                    page=(offset // PAGE_SIZE + 1) if other else n,
                    secondary_page=n if other else (offset2 // PAGE_SIZE + 1),
                )
            return {
                "items": rows,
                "next": url(pg + 1) if raw.get("has_more") else None,
                "previous": url(pg - 1) if pg > 1 else None,
                "coverage_state": raw.get("coverage_state"),
            }

        collections = []
        for key, label, is_second in (
            ("offers", "Offres de cette activité", False),
            ("services", "Services de cette route", False),
            ("departures", "Départs liés", kind == "transport_route"),
            ("lines", "Lignes de commande", False),
        ):
            if key in detail:
                collections.append({
                    "key": key, "label": label,
                    **linked_collection(key, other=is_second),
                })

        if self.request.GET.get("origin") == "parent" and activity:
            parent = build_space_work_projection(
                profile=self.request.user, space=self.space,
                responsibility_key=responsibility,
                source_kind="activity", source_id=str(activity.pk),
            )
            if (parent or {}).get("selection"):
                back_url = g3_depth_url(
                    self.space, "activity", activity.pk,
                    responsibility=responsibility,
                    origin_section=origin_section,
                )
                back_label = "Retour au service"

        context["work_g3"] = {
            "kind": kind,
            "title": selection["title"],
            "summary": selection.get("summary"),
            "status": (selection.get("context") or {}).get(
                "owner_state_label"
            ) or selection.get("state"),
            "facts": detail.get("facts") or {},
            "context": selection.get("context") or {},
            "timing": selection.get("timing") or {},
            "is_commerce": is_commerce,
            "actions": actions,
            "collections": collections,
            "parent": linked_activity,
            "back_url": back_url,
            "back_label": back_label,
        }
        restore_work_origin(
            request=self.request, context=context, context_key="work_g3",
            space=self.space, responsibility=responsibility,
            section=origin_section,
        )
        return context
