from __future__ import annotations

from django.http import Http404
from django.urls import reverse

from .api.space_work_projection import build_space_work_projection
from .space_web_views import SpaceWebMixin


SECTION_EMPTY_MESSAGES = {
    "preparation": "Rien à préparer pour le moment.",
    "upcoming": "Rien à venir pour le moment.",
    "active": "Rien en cours pour le moment.",
    "blocked": "Aucun blocage projeté pour le moment.",
    "completed": "Rien de terminé dans cette vue pour le moment.",
    "activities": "Aucun programme visible pour le moment.",
    "offers": "Aucune offre visible pour le moment.",
    "routes": "Aucune route visible pour le moment.",
    "vehicles": "Aucun véhicule visible pour le moment.",
}


def _activity_owner_url(space, item):
    """Return an existing owner-backed Web handoff only when ZS3 exposes an Activity link."""

    links = item.get("links") or {}
    source = item.get("source") or {}
    context = item.get("context") or {}
    capabilities = set(item.get("capabilities") or ())

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
    composed = []
    for key, section in sections.items():
        label = section.get("representation") or key.replace("_", " ").title()
        if key == "activities" and section.get("role") == "structure":
            label = f"Structure · {label}"
        items = []
        for raw_item in section.get("items") or ():
            item = dict(raw_item)
            item["owner_url"] = _activity_owner_url(space, item)
            items.append(item)
        composed.append(
            {
                "key": key,
                "label": label,
                "empty_message": SECTION_EMPTY_MESSAGES.get(
                    key, f"Aucun élément visible dans {label.lower()} pour le moment."
                ),
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
