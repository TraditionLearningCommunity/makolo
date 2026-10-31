from __future__ import annotations

from django.http import Http404
from django.urls import reverse

from .api.space_work_projection import build_space_work_projection
from .space_web_views import SpaceWebMixin



def _activity_owner_url(space, item):
    """Return an existing owner-backed Web handoff only when ZS3 exposes an Activity link."""

    links = item.get("links") or {}
    source = item.get("source") or {}
    context = item.get("context") or {}
    capabilities = set(item.get("capabilities") or ())

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


def _compose_sections(space, projection):
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
        if not raw_items:
            continue
        label = section.get("representation") or key.replace("_", " ").title()
        items = []
        for raw_item in raw_items:
            item = dict(raw_item)
            item["owner_url"] = _activity_owner_url(space, item)
            item["owner_label"] = (
                "Ouvrir le dossier"
                if item.get("kind") == "service_case" and item["owner_url"]
                else "Voir le programme"
                if item.get("kind") == "journey" and item["owner_url"]
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

        sections = _compose_sections(self.space, projection)
        context.update(
            {
                "projection": projection,
                "work_sections": sections,
                "work_has_items": any(section["items"] for section in sections),
            }
        )
        return context
