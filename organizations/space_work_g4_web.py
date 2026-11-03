"""MT6: Creative/Media N2 from authorized Activity and Occurrence owners."""
from urllib.parse import urlencode

from django.http import Http404
from django.urls import reverse

from activities.models import Activity, Occurrence
from authorization.constants import PermissionCode
from authorization.services import can
from organizations.models import SpaceArchetype

from .api.space_work_projection import build_space_work_projection
from .space_web_views import SpaceWebMixin
from .space_work_navigation import restore_work_origin


_ARCHETYPES = {SpaceArchetype.CREATIVE, SpaceArchetype.MEDIA}
_SECTIONS = {
    "activities", "preparation", "active", "upcoming", "completed",
    "offers", "requests", "blocked",
}
_LIMIT = 12


def _page(raw):
    if not raw.isdecimal() or len(raw) > 4 or not 1 <= int(raw) <= 834:
        raise Http404
    return int(raw)


def _depth_url(space, kind, identity, responsibility, section, *, page=None,
               from_activity=False):
    url = reverse(
        "organizations:space-work-depth-g4",
        kwargs={"slug": space.slug, "kind": kind, "owner_id": identity},
    )
    query = {"responsibility": responsibility, "from": section}
    if page is not None:
        query["page"] = page
    if from_activity:
        query["origin"] = "activity"
    return url + "?" + urlencode(query)


class SpaceWorkG4DepthView(SpaceWebMixin):
    """N2 with source selection and rights revalidated on each GET."""

    template_name = "organizations/space/work_g4_depth.html"
    space_nav_key = "work"
    space_page_title = "Métier"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.space.archetype not in _ARCHETYPES:
            raise Http404
        kind = self.kwargs["kind"]
        if kind not in {"activity", "occurrence"}:
            raise Http404
        owner_id = str(self.kwargs["owner_id"])
        section = self.request.GET.get("from", "activities")
        if section not in _SECTIONS:
            section = "activities"
        page = _page(self.request.GET.get("page", "1"))
        responsibility = self.selected_responsibility["key"]
        projection = build_space_work_projection(
            profile=self.request.user, space=self.space,
            responsibility_key=responsibility, source_kind=kind,
            source_id=owner_id,
            related_offset=(page - 1) * _LIMIT if kind == "activity" else 0,
        )
        selected = (projection or {}).get("selection")
        if not selected or selected.get("source") != {
            "kind": kind, "id": owner_id,
        }:
            raise Http404
        parent_id = (
            owner_id if kind == "activity"
            else (selected.get("context") or {}).get("activity", {}).get("id")
        )
        activity = Activity.objects.filter(
            pk=parent_id, space=self.space,
        ).first() if parent_id else None
        if activity is None:
            raise Http404

        creative = self.space.archetype == SpaceArchetype.CREATIVE
        noun = "création" if creative else "production"
        back_url = self._space_nav_url("organizations:space-work") + "#work-" + section
        back_label = "Retour aux créations" if creative else "Retour aux productions"
        parent_url = None
        if kind == "occurrence":
            parent_projection = build_space_work_projection(
                profile=self.request.user, space=self.space,
                responsibility_key=responsibility,
                source_kind="activity", source_id=str(activity.pk),
            )
            if (parent_projection or {}).get("selection"):
                parent_url = _depth_url(
                    self.space, "activity", activity.pk, responsibility, section,
                    page=page,
                )
                if self.request.GET.get("origin") == "activity":
                    back_url = parent_url
                    back_label = "Retour à la " + noun

        actions = []
        if kind == "activity":
            if "manage" in selected.get("capabilities", ()) and can(
                self.request.user, PermissionCode.ACTIVITY_MANAGE, activity=activity,
            ):
                actions.extend([
                    {
                        "label": "Gérer la " + noun,
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
                    {
                        "label": "Présentations et médias",
                        "url": reverse(
                            "presentations:studio",
                            kwargs={"activity_id": activity.pk},
                        ),
                    },
                ])
        elif (
            "open_day_of" in selected.get("capabilities", ())
            and (selected.get("links") or {}).get("day_of")
        ):
            actions.append({
                "label": "Ouvrir Jour J",
                "url": reverse(
                    "organizations:space-occurrence-day-of",
                    kwargs={"slug": self.space.slug, "occurrence_id": owner_id},
                ) + "?" + urlencode({"responsibility": responsibility}),
            })

        dates = selected.get("related_occurrences") or {}
        related = []
        if kind == "activity":
            for row in dates.get("items", ()):
                source = row.get("source") or {}
                related.append({
                    **row,
                    "url": _depth_url(
                        self.space, "occurrence", source["id"], responsibility,
                        section, page=page, from_activity=True,
                    ) if row.get("openable") else None,
                })
        if kind == "activity":
            status = activity.get_status_display()
        else:
            occurrence = Occurrence.objects.filter(
                pk=owner_id, activity=activity,
            ).first()
            if occurrence is None:
                raise Http404
            status = occurrence.get_status_display()

        detail = selected.get("g4_detail") or {}
        context["work_g4"] = {
            "kind": kind,
            "title": selected["title"],
            "summary": selected.get("summary"),
            "description": detail.get("description"),
            "status": status,
            "creative": creative,
            "activity": kind == "activity",
            "occurrence": kind == "occurrence",
            "context": selected.get("context") or {},
            "timing": selected.get("timing") or {},
            "media": (selected.get("media_bindings") or [None])[0],
            "next_occurrence": (selected.get("context") or {}).get("next_occurrence"),
            "related_label": detail.get("related_label"),
            "related": related,
            "previous": _depth_url(
                self.space, kind, owner_id, responsibility, section, page=page - 1,
            ) if kind == "activity" and page > 1 else None,
            "next": _depth_url(
                self.space, kind, owner_id, responsibility, section, page=page + 1,
            ) if kind == "activity" and dates.get("has_more") else None,
            "actions": actions,
            "back_url": back_url,
            "back_label": back_label,
            "parent_url": parent_url,
        }
        restore_work_origin(
            request=self.request, context=context, context_key="work_g4",
            space=self.space, responsibility=responsibility,
            section=section,
        )
        return context
