"""MT4: Education/Service Provider N2 presentation; actual owners keep authority."""
from urllib.parse import urlencode

from django.http import Http404
from django.urls import reverse

from activities.models import Activity, Occurrence
from authorization.constants import PermissionCode
from authorization.services import can
from journeys.models import Journey
from organizations.models import SpaceArchetype
from services.models import ServiceDetails

from .api.space_work_projection import build_space_work_projection
from .space_web_views import SpaceWebMixin
from .space_work_navigation import restore_work_origin


_G2_ARCHETYPES = {
    SpaceArchetype.EDUCATION, SpaceArchetype.SERVICE_PROVIDER,
}
_G2_KINDS = {"activity", "occurrence", "journey"}
_ROOT_SECTIONS = {
    "activities", "preparation", "upcoming", "active", "blocked",
    "completed", "requests",
}
_REL_LIMIT = 12


def _page_offset(request, field):
    raw = (request.GET.get(field) or "1").strip()
    if not raw.isdecimal() or len(raw) > 4 or not 1 <= int(raw) <= 834:
        raise Http404
    return (int(raw) - 1) * _REL_LIMIT


def _g2_depth_url(space, kind, identity, *, responsibility, origin_section,
                  origin="root", page=None, work_page=None):
    url = reverse(
        "organizations:space-work-depth-g2",
        kwargs={"slug": space.slug, "kind": kind, "owner_id": identity},
    )
    params = {"responsibility": responsibility, "from": origin_section}
    if origin == "activity":
        params["origin"] = origin
    if page is not None:
        params["page"] = page
    if work_page is not None:
        params["work_page"] = work_page
    return f"{url}?{urlencode(params)}"


class SpaceWorkG2DepthView(SpaceWebMixin):
    """Programme/Prestation, Session/Occurrence or Journey, server-selected."""

    template_name = "organizations/space/work_g2_depth.html"
    space_nav_key = "work"
    space_page_title = "Métier"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.space.archetype not in _G2_ARCHETYPES:
            raise Http404
        kind = self.kwargs["kind"]
        owner_id = str(self.kwargs["owner_id"])
        if kind not in _G2_KINDS:
            raise Http404
        responsibility = self.selected_responsibility["key"]
        is_education = self.space.archetype == SpaceArchetype.EDUCATION
        origin_section = self.request.GET.get("from", "activities")
        if origin_section not in _ROOT_SECTIONS:
            origin_section = "activities"
        occ_offset = _page_offset(self.request, "page") if kind == "activity" else 0
        work_offset = _page_offset(self.request, "work_page") if kind == "activity" else 0
        projection = build_space_work_projection(
            profile=self.request.user, space=self.space,
            responsibility_key=responsibility,
            source_kind=kind, source_id=owner_id,
            related_offset=occ_offset, related_work_offset=work_offset,
        )
        selection = (projection or {}).get("selection")
        if not selection or selection.get("source") != {
            "kind": kind, "id": owner_id,
        }:
            raise Http404

        activity_id = (
            owner_id if kind == "activity"
            else (selection.get("context") or {}).get("activity", {}).get("id")
        )
        activity = (
            Activity.objects.filter(pk=activity_id, space=self.space).first()
            if activity_id else None
        )
        if activity is None:
            raise Http404
        root_url = self._space_nav_url("organizations:space-work")
        back_label = "Retour aux programmes" if is_education else "Retour aux prestations"
        back_url = f"{root_url}#work-{origin_section}"
        parent_url = None
        if kind != "activity":
            parent_projection = build_space_work_projection(
                profile=self.request.user, space=self.space,
                responsibility_key=responsibility, source_kind="activity",
                source_id=str(activity.pk),
            )
            if (parent_projection or {}).get("selection"):
                parent_url = _g2_depth_url(
                    self.space, "activity", activity.pk,
                    responsibility=responsibility,
                    origin_section=origin_section,
                    page=self.request.GET.get("page") if (
                        self.request.GET.get("page", "").isdecimal()
                        and len(self.request.GET["page"]) <= 4
                        and 1 <= int(self.request.GET["page"]) <= 834
                    ) else None,
                    work_page=self.request.GET.get("work_page") if (
                        self.request.GET.get("work_page", "").isdecimal()
                        and len(self.request.GET["work_page"]) <= 4
                        and 1 <= int(self.request.GET["work_page"]) <= 834
                    ) else None,
                )
                if self.request.GET.get("origin") == "activity":
                    back_url = parent_url
                    back_label = "Retour au programme" if is_education else "Retour à la prestation"

        actions = []
        if kind == "activity":
            if can(self.request.user, PermissionCode.ACTIVITY_MANAGE, activity=activity):
                actions.append({
                    "label": "Gérer les ressources",
                    "url": reverse(
                        "preparation:manage",
                        kwargs={"activity_id": activity.pk},
                    ),
                })
                if is_education:
                    # Canonical Forms owner, no ProgrammeForm copy.
                    actions.append({
                        "label": "Gérer les formulaires",
                        "url": reverse(
                            "questionnaires:manage",
                            kwargs={"activity_id": activity.pk},
                        ),
                    })
            if not is_education:
                # Configuration belongs to Services, not this N2.
                service = ServiceDetails.objects.filter(activity=activity).first()
                if (
                    service is not None and can(
                        self.request.user,
                        PermissionCode.ACTIVITY_SERVICES_CONFIGURE,
                        activity=activity,
                    )
                ):
                    actions.append({
                        "label": "Configurer la prestation",
                        "url": reverse(
                            "services:operator-service-config",
                            kwargs={"service_pk": service.pk},
                        ),
                    })
        elif kind == "occurrence" and "open_day_of" in selection.get("capabilities", ()):
            if (selection.get("links") or {}).get("day_of"):
                actions.append({
                    "label": "Ouvrir Jour J",
                    "url": reverse(
                        "organizations:space-occurrence-day-of",
                        kwargs={"slug": self.space.slug, "occurrence_id": owner_id},
                    ) + "?" + urlencode({"responsibility": responsibility}),
                })
        elif kind == "journey":
            for handoff in selection.get("owner_handoffs") or ():
                if handoff.get("intent") == "open_request" and is_education:
                    request_owner = handoff.get("owner") or {}
                    if request_owner.get("kind") == "journey_request":
                        actions.append({
                            "label": "Examiner l'inscription",
                            "url": reverse(
                                "organizations:console-requests",
                                kwargs={"slug": self.space.slug},
                            ) + "?" + urlencode({
                                "request": request_owner["id"],
                                "activity": str(activity.pk),
                                "status": "all",
                            }),
                        })
                if (
                    handoff.get("intent") == "open_service_case"
                    and not is_education
                    and handoff.get("channel") == "web"
                ):
                    actions.append({
                        "label": "Travailler sur le dossier",
                        "url": handoff["url"],
                    })

        occurrences = selection.get("related_occurrences") or {}
        related = []
        if kind == "activity":
            for row in occurrences.get("items", ()):
                source = row.get("source") or {}
                related.append({
                    **row,
                    "url": (
                        _g2_depth_url(
                            self.space, "occurrence", source["id"],
                            responsibility=responsibility,
                            origin_section=origin_section, origin="activity",
                            page=(occ_offset // _REL_LIMIT + 1) if occ_offset else None,
                            work_page=(work_offset // _REL_LIMIT + 1) if work_offset else None,
                        ) if row.get("openable") else None
                    ),
                })
        related_work = selection.get("related_work") or {}
        linked_work = []
        if kind == "activity":
            for row in related_work.get("items", ()):
                source = row.get("source") or {}
                linked_work.append({
                    **row,
                    "url": _g2_depth_url(
                        self.space, "journey", source["id"],
                        responsibility=responsibility,
                        origin_section=origin_section, origin="activity",
                        page=(occ_offset // _REL_LIMIT + 1) if occ_offset else None,
                        work_page=(work_offset // _REL_LIMIT + 1) if work_offset else None,
                    ),
                })
        occ_page = occ_offset // _REL_LIMIT + 1
        work_page = work_offset // _REL_LIMIT + 1
        def _page_url(*, page, work_page):
            return _g2_depth_url(
                self.space, "activity", activity.pk,
                responsibility=responsibility,
                origin_section=origin_section, page=page, work_page=work_page,
            )

        if kind == "activity":
            owner_status = activity.get_status_display()
        elif kind == "occurrence":
            occurrence = Occurrence.objects.filter(
                pk=owner_id, activity=activity,
            ).first()
            if occurrence is None:
                raise Http404
            owner_status = occurrence.get_status_display()
        else:
            journey = Journey.objects.filter(pk=owner_id, activity=activity).first()
            if journey is None:
                raise Http404
            owner_status = journey.get_status_display()
        context.update({
            "work_g2": {
                "kind": kind,
                "identity": selection["entry_identity"],
                "title": selection["title"],
                "summary": selection.get("summary"),
                "status": owner_status,
                "context": selection.get("context") or {},
                "timing": selection.get("timing") or {},
                "is_education": is_education,
                "is_activity": kind == "activity",
                "is_occurrence": kind == "occurrence",
                "is_journey": kind == "journey",
                "actions": actions,
                "related": related,
                "linked_work": linked_work,
                "next_occurrences": (
                    _page_url(page=occ_page + 1, work_page=work_page)
                    if occurrences.get("has_more") else None
                ),
                "previous_occurrences": (
                    _page_url(page=occ_page - 1, work_page=work_page)
                    if occ_page > 1 else None
                ),
                "next_work": (
                    _page_url(page=occ_page, work_page=work_page + 1)
                    if related_work.get("has_more") else None
                ),
                "previous_work": (
                    _page_url(page=occ_page, work_page=work_page - 1)
                    if work_page > 1 else None
                ),
                "parent_url": parent_url,
                "back_url": back_url,
                "back_label": back_label,
            },
        })
        restore_work_origin(
            request=self.request, context=context, context_key="work_g2",
            space=self.space, responsibility=responsibility,
            section=origin_section,
        )
        return context
