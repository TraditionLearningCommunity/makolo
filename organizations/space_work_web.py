from __future__ import annotations

from django.http import Http404
from urllib.parse import urlencode
from django.urls import reverse

from authorization.constants import PermissionCode
from authorization.selectors import has_direct_space_permission
from organizations.models import SpaceArchetype

from .api.space_work_projection import PREVIEW_LIMIT, build_space_work_projection
from .space_work_navigation import (
    MAX_WORK_PAGE, WORK_SECTIONS, work_back_url, work_page_number,
)
from .space_web_views import SpaceWebMixin



def _activity_owner_url(space, item, *, profile=None, responsibility="all", section_key="activities"):
    """Return an existing owner-backed Web handoff only when ZS3 exposes an Activity link."""

    links = item.get("links") or {}
    source = item.get("source") or {}
    context = item.get("context") or {}
    capabilities = set(item.get("capabilities") or ())

    # Existing owner views always authorize again at navigation time.
    direct_portfolio = (
        profile is not None
        and has_direct_space_permission(
            profile, space, PermissionCode.SPACE_ACTIVITIES_VIEW
        )
    )
    source_kind = source.get("kind")
    if (
        (space.archetype == SpaceArchetype.COMMERCE
         and source_kind in {"offer", "commerce_order", "activity"})
        or
        (space.archetype == SpaceArchetype.TRANSPORT_OPERATOR
         and source_kind in {"activity", "occurrence", "transport_route", "vehicle"})
    ) and "view" in capabilities and source.get("id"):
        return reverse(
            "organizations:space-work-depth-g3",
            kwargs={
                "slug": space.slug, "kind": source_kind,
                "owner_id": source["id"],
            },
        ) + "?" + urlencode({
            "responsibility": responsibility,
            "from": section_key,
        })
    if (
        space.archetype in {SpaceArchetype.CREATIVE, SpaceArchetype.MEDIA}
        and source_kind in {"activity", "occurrence"}
        and "view" in capabilities and source.get("id")
    ):
        return reverse(
            "organizations:space-work-depth-g4",
            kwargs={"slug": space.slug, "kind": source_kind,
                    "owner_id": source["id"]},
        ) + "?" + urlencode({
            "responsibility": responsibility, "from": section_key,
        })
    if (
        space.archetype in {
            SpaceArchetype.EDUCATION, SpaceArchetype.SERVICE_PROVIDER,
        }
        and source_kind in {"activity", "occurrence", "journey"}
        and "view" in capabilities
        and source.get("id")
    ):
        path = reverse(
            "organizations:space-work-depth-g2",
            kwargs={
                "slug": space.slug, "kind": source_kind,
                "owner_id": source["id"],
            },
        )
        return path + "?" + urlencode({
            "responsibility": responsibility,
            "from": section_key,
        })
    # G1 now has a real N2, not a direct jump into the Console.
    # The N2 owner read revalidates scope and selection on every visit.
    if (
        space.archetype in {SpaceArchetype.GENERIC, SpaceArchetype.COMMUNITY}
        and source_kind in {"activity", "occurrence", "journey"}
        and "view" in capabilities
        and source.get("id")
    ):
        path = reverse(
            "organizations:space-work-depth",
            kwargs={
                "slug": space.slug, "kind": source_kind,
                "owner_id": source["id"],
            },
        )
        return path + "?" + urlencode({
            "responsibility": responsibility,
            "from": section_key,
        })
    if source_kind == "commerce_order":
        if responsibility == "all" and links.get("detail"):
            return reverse(
                "organizations:space-retrieval-order-detail",
                kwargs={"slug": space.slug, "order_id": source["id"]},
            )
        return None
    if source_kind == "offer":
        if "open_commerce" in capabilities or direct_portfolio:
            return reverse("organizations:console-offers", kwargs={"slug": space.slug})
        return None
    if source_kind == "transport_route":
        if direct_portfolio and responsibility == "all":
            return reverse(
                "organizations:console-transport-route-detail",
                kwargs={"slug": space.slug, "route_id": source["id"]},
            )
        return None
    if source_kind == "vehicle":
        if direct_portfolio and responsibility == "all":
            return reverse("organizations:console-transport", kwargs={"slug": space.slug})
        return None
    if (
        source_kind == "occurrence"
        and context.get("transport", {}).get("departure_id")
        and direct_portfolio and "open_operations" in capabilities
    ):
        return reverse(
            "organizations:console-transport-departure-detail",
            kwargs={
                "slug": space.slug,
                "departure_id": context["transport"]["departure_id"],
            },
        )

    # An operator Service case is a real owner depth; the generic Activity
    # Console may be inaccessible to an assigned case operator.
    if item.get("kind") == "service_case":
        if "open_service_case" in capabilities and links.get("detail"):
            return links["detail"]
        return None

    activity_id = None
    if source.get("kind") == "activity" and links.get("detail"):
        activity_id = source.get("id")
    elif links.get("activity"):
        activity_id = (context.get("activity") or {}).get("id")

    if not activity_id or "view" not in capabilities:
        return None

    return reverse(
        "organizations:console-activity-detail",
        kwargs={"slug": space.slug, "activity_id": activity_id},
    )


def _compose_sections(space, projection, *, profile=None, origin_page=None):
    sections = projection.get("sections") or {}
    section_order = (
        (projection.get("presentation") or {}).get("section_order")
        or tuple(sections)
    )
    # Reading groups are already composed by the server's Presentation layer.
    # Web only associates each group heading with its first visible section.
    chapters = {}
    for group in (projection.get("business_world") or {}).get("reading_groups", ()):
        for index, key in enumerate(group.get("section_keys", ())):
            chapters[key] = group.get("representation") if index == 0 else None
    composed = []
    for key in section_order:
        section = sections.get(key) or {}
        raw_items = section.get("items") or ()
        if not raw_items and not section.get("has_more"):
            continue
        label = section.get("representation") or key.replace("_", " ").title()
        items = []
        for raw_item in raw_items:
            item = dict(raw_item)
            item["owner_url"] = _activity_owner_url(
                space, item, profile=profile,
                responsibility=projection.get("responsibility", "all"),
                section_key=key,
            )
            if (
                origin_page is not None
                and item["owner_url"]
                and "/work/" in item["owner_url"]
            ):
                item["owner_url"] += (
                    ("&" if "?" in item["owner_url"] else "?")
                    + urlencode({"work_origin_page": origin_page})
                )
            # Owner-supplied Web handoffs only. API/space_work handoffs do
            # not become browser mutations or unverified destinations.
            item["web_handoffs"] = [
                {"label": handoff["label"], "url": handoff["url"]}
                for handoff in item.get("owner_handoffs", ())
                if (
                    handoff.get("intent") == "open_service_case"
                    and handoff.get("channel") == "web"
                    and handoff.get("owner") == item.get("source")
                    and handoff.get("url") == (item.get("links") or {}).get("detail")
                    and "open_service_case" in item.get("capabilities", ())
                    and handoff.get("label")
                )
            ]
            item["owner_label"] = (
                "Voir l’offre"
                if item["owner_url"] and space.archetype == SpaceArchetype.COMMERCE
                and item["source"]["kind"] == "offer"
                else "Voir la commande"
                if item["owner_url"] and space.archetype == SpaceArchetype.COMMERCE
                and item["source"]["kind"] == "commerce_order"
                else "Voir la route"
                if item["owner_url"] and space.archetype == SpaceArchetype.TRANSPORT_OPERATOR
                and item["source"]["kind"] == "transport_route"
                else "Voir le véhicule"
                if item["owner_url"] and space.archetype == SpaceArchetype.TRANSPORT_OPERATOR
                and item["source"]["kind"] == "vehicle"
                else "Voir le départ"
                if item["owner_url"] and space.archetype == SpaceArchetype.TRANSPORT_OPERATOR
                and item["source"]["kind"] == "occurrence" and item.get("kind") == "departure"
                else "Voir le service"
                if item["owner_url"] and space.archetype == SpaceArchetype.TRANSPORT_OPERATOR
                and item["source"]["kind"] == "activity"
                else "Voir le programme"
                if item["owner_url"] and space.archetype == SpaceArchetype.EDUCATION
                and item["source"]["kind"] == "activity"
                else "Voir la session"
                if item["owner_url"] and space.archetype == SpaceArchetype.EDUCATION
                and item["source"]["kind"] == "occurrence"
                else "Voir l'inscription"
                if item["owner_url"] and space.archetype == SpaceArchetype.EDUCATION
                and item["source"]["kind"] == "journey"
                else "Voir la prestation"
                if item["owner_url"] and space.archetype == SpaceArchetype.SERVICE_PROVIDER
                and item["source"]["kind"] == "activity"
                else "Voir la réalisation"
                if item["owner_url"] and space.archetype == SpaceArchetype.SERVICE_PROVIDER
                and item["source"]["kind"] == "occurrence"
                else "Ouvrir le dossier"
                if item["owner_url"] and space.archetype == SpaceArchetype.SERVICE_PROVIDER
                and item["source"]["kind"] == "journey"
                else "Voir la création"
                if item["owner_url"] and space.archetype == "creative"
                and item["source"]["kind"] == "activity"
                else "Voir la production"
                if item["owner_url"] and space.archetype == "media"
                and item["source"]["kind"] == "activity"
                else "Ouvrir le dossier"
                if item.get("kind") == "service_case" and item["owner_url"]
                else "Voir le programme"
                if item.get("kind") == "journey" and item["owner_url"]
                else "Voir la commande"
                if item.get("kind") == "order" and item["owner_url"]
                else "Voir les offres"
                if item.get("kind") == "offer" and item["owner_url"]
                else "Voir la route"
                if item.get("kind") == "route" and item["owner_url"]
                else "Voir les véhicules"
                if item.get("kind") == "vehicle" and item["owner_url"]
                else "Ouvrir le départ"
                if item.get("kind") == "departure" and item["owner_url"]
                else "Voir l’initiative"
                if item["owner_url"] and space.archetype == SpaceArchetype.COMMUNITY
                and item["source"]["kind"] == "activity"
                else "Voir l’activité"
                if item["owner_url"] and space.archetype == SpaceArchetype.GENERIC
                and item["source"]["kind"] == "activity"
                else "Voir la réalisation"
                if item["owner_url"] and space.archetype in {
                    SpaceArchetype.GENERIC, SpaceArchetype.COMMUNITY,
                } and item["source"]["kind"] == "occurrence"
                else "Ouvrir la démarche"
                if item["owner_url"] and space.archetype in {
                    SpaceArchetype.GENERIC, SpaceArchetype.COMMUNITY,
                } and item["source"]["kind"] == "journey"
                else "Ouvrir"
            )
            items.append(item)
        composed.append(
            {
                "key": key,
                "label": label,
                "chapter_title": chapters.get(key),
                "role": section.get("role") or "continuity",
                "items": items,
                "has_more": bool(section.get("has_more")),
                "links": section.get("links") or {},
                "continuation_url": (
                    reverse(
                        "organizations:space-work-collection",
                        kwargs={"slug": space.slug, "section": key},
                    ) + "?" + urlencode({
                        "responsibility": projection.get("responsibility", "all"),
                        "page": (origin_page + 1) if origin_page is not None else 2,
                    })
                ) if (
                    section.get("has_more")
                    and (origin_page is None or origin_page < MAX_WORK_PAGE)
                ) else None,
            }
        )
    return tuple(composed)



class SpaceWorkView(SpaceWebMixin):
    """Durable Space work surface consuming the ZS3 projection without rebuilding domain truth."""

    template_name = "organizations/space/work.html"
    space_nav_key = "work"

    @property
    def space_page_title(self):
        return (
            self.workspace.get("operating_preset", {}).get("primary_business_label")
            or "Métier"
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        projection = build_space_work_projection(
            profile=self.request.user,
            space=self.space,
            responsibility_key=self.selected_responsibility["key"],
        )
        if projection is None:
            raise Http404

        sections = _compose_sections(
            self.space, projection, profile=self.request.user
        )
        context.update(
            {
                "projection": projection,
                "work_sections": sections,
                "work_has_items": any(
                    section["items"] or section["has_more"] for section in sections
                ),
                "work_is_collection": False,
                "work_search_url": self._space_nav_url(
                    "organizations:space-search"
                ),
                "work_history_url": self._space_nav_url(
                    "organizations:space-history"
                ),
                "work_g3_transport_url": reverse(
                    "organizations:console-transport",
                    kwargs={"slug": self.space.slug},
                ) if (
                    projection["capabilities"].get("create_transport")
                    and self.selected_responsibility["key"] == "all"
                ) else None,
                "work_g2_create_label": (
                    "Nouveau programme"
                    if self.space.archetype == SpaceArchetype.EDUCATION
                    else "Nouvelle prestation"
                    if self.space.archetype == SpaceArchetype.SERVICE_PROVIDER
                    else None
                ) if (
                    projection["capabilities"].get("create_g2")
                    and self.selected_responsibility["key"] == "all"
                ) else None,
                "work_g2_create_url": reverse(
                    "organizations:space-work-create-g2",
                    kwargs={"slug": self.space.slug},
                ) if (
                    projection["capabilities"].get("create_g2")
                    and self.selected_responsibility["key"] == "all"
                ) else None,
                "work_create_label": (
                    "Nouvelle initiative"
                    if self.space.archetype == SpaceArchetype.COMMUNITY
                    else "Nouvelle activité"
                    if self.space.archetype == SpaceArchetype.GENERIC
                    else "Nouvelle création"
                    if self.space.archetype == SpaceArchetype.CREATIVE
                    else "Nouvelle production"
                    if self.space.archetype == SpaceArchetype.MEDIA
                    else None
                ) if (
                    projection["capabilities"].get("create_activity")
                    and self.selected_responsibility["key"] == "all"
                ) else None,
                "work_create_url": (
                    reverse("activities:create") + "?"
                    + urlencode({"space": self.space.slug})
                ) if (
                    self.space.archetype in {
                        SpaceArchetype.GENERIC, SpaceArchetype.COMMUNITY,
                        SpaceArchetype.CREATIVE, SpaceArchetype.MEDIA,
                    }
                    and projection["capabilities"].get("create_activity")
                    and self.selected_responsibility["key"] == "all"
                ) else None,
            }
        )
        return context


class SpaceWorkCollectionView(SpaceWebMixin):
    """MT7: one explicit bounded Work collection, same owner projections.

    No infinite scroll or client-side reconstruction of hidden items. The
    authorization is recomputed on every page, including direct deep links.
    """

    template_name = "organizations/space/work.html"
    space_nav_key = "work"
    space_page_title = "Métier"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        section_key = self.kwargs["section"]
        if section_key not in WORK_SECTIONS:
            raise Http404
        page = work_page_number(self.request.GET.get("page"), required=True)
        responsibility = self.selected_responsibility["key"]
        projection = build_space_work_projection(
            profile=self.request.user,
            space=self.space,
            responsibility_key=responsibility,
            section_key=section_key,
            offset=(page - 1) * PREVIEW_LIMIT,
        )
        if projection is None:
            raise Http404
        sections = _compose_sections(
            self.space, projection, profile=self.request.user, origin_page=page,
        )
        section = (projection.get("sections") or {}).get(section_key) or {}
        section_label = section.get("representation") or "Métier"
        base = reverse(
            "organizations:space-work-collection",
            kwargs={"slug": self.space.slug, "section": section_key},
        )

        def page_url(number):
            return base + "?" + urlencode({
                "responsibility": responsibility, "page": number,
            })

        context.update({
            "projection": projection,
            "work_sections": sections,
            "work_has_items": any(
                s["items"] or s["has_more"] for s in sections
            ),
            "work_is_collection": True,
            "work_search_url": self._space_nav_url(
                "organizations:space-search"
            ),
            "work_history_url": self._space_nav_url(
                "organizations:space-history"
            ),
            "work_collection_title": section_label,
            "work_collection_page": page,
            "work_collection_empty": (
                "Aucun autre élément dans cette page."
                if page > 1 else section.get("empty_message")
            ),
            "work_root_url": work_back_url(
                space=self.space, responsibility=responsibility,
                section=section_key,
            ),
            "work_previous_url": page_url(page - 1) if page > 1 else None,
            "work_next_url": page_url(page + 1)
            if section.get("has_more") and page < MAX_WORK_PAGE else None,
        })
        return context
