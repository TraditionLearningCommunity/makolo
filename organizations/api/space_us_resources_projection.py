"""Space-owned resources for Nous: compose established owners, never copy files.

This is a bounded read model. It is not an asset store or an authorization
grant: Sharing owns issued Passport documents and Presentation owns reusable
templates/themes. PersonalAsset and ActivityResource never become Space assets.
"""
from __future__ import annotations

from authorization.constants import PermissionCode
from authorization.selectors import has_direct_space_permission
from presentations.enums import VersionStatus
from presentations.models import PresentationTemplateVersion, PresentationThemeVersion
from sharing.models import PassportSnapshot

PAGE_SIZE = 20
PREVIEW_LIMIT = 3
RESOURCE_KINDS = ("passport", "template", "theme")
# These are the currently established institutional owners, not a claim
# that every kind of corporate document has a canonical Makolo owner.
RESOURCE_COVERAGE = {
    "state": "partial",
    "owners": ["sharing.passport", "presentations.library"],
}


def can_view_space_resources(*, profile, space):
    """The included private documents require current institutional authority."""
    return has_direct_space_permission(profile, space, PermissionCode.SPACE_MANAGE)


def _families(space):
    return {
        "passport": PassportSnapshot.objects.filter(
            space=space, revoked_at__isnull=True
        ).order_by("-generated_at", "-pk"),
        "template": PresentationTemplateVersion.objects.filter(
            template__owner_space=space,
            status=VersionStatus.PUBLISHED,
        ).select_related("template").order_by("-published_at", "-pk"),
        "theme": PresentationThemeVersion.objects.filter(
            theme__owner_space=space,
            status=VersionStatus.PUBLISHED,
        ).select_related("theme").order_by("-published_at", "-pk"),
    }


def _item(kind, row, *, slug):
    if kind == "passport":
        return {
            "kind": kind,
            "id": str(row.pk),
            "title": "Passeport Makolo · " + row.document_id,
            "detail": "Document institutionnel émis · " + row.variant,
            "issued_at": row.generated_at.isoformat(),
            "owner": "sharing",
            "handoff": f"/space/{slug}/us/passport",
        }
    subject = row.template if kind == "template" else row.theme
    return {
        "kind": kind,
        "id": str(row.pk),
        "title": subject.name,
        "detail": (
            "Modèle de présentation" if kind == "template"
            else "Thème de présentation"
        ) + f" · version {row.version_number}",
        "issued_at": row.published_at.isoformat() if row.published_at else None,
        "owner": "presentations",
        # The Presentation library is Web-owner-backed. Do not invent a
        # mobile route to it or hand back arbitrary storage locations.
        "handoff": None,
    }


def build_space_us_resources_projection(
    *, profile, space, kind=None, offset=0, preview=False
):
    """Return only authorized Space subject/ownership sources, without blobs."""
    if not can_view_space_resources(profile=profile, space=space):
        return None
    if kind is not None and kind not in RESOURCE_KINDS:
        raise ValueError("Unknown resource kind")
    if not isinstance(offset, int) or offset < 0 or offset > 100000:
        raise ValueError("Invalid resource offset")

    families = _families(space)
    counts = {name: qs.count() for name, qs in families.items()}
    total = sum(counts.values())
    if preview:
        # One preview per actual owner family prevents many Passport
        # revisions from drowning out reusable institutional resources.
        items = []
        for name in ("template", "theme", "passport"):
            items.extend(
                _item(name, row, slug=space.slug)
                for row in families[name][:1]
            )
        return {
            "space_id": str(space.pk),
            "visibility": "visible",
            "items": items,
            "count": total,
            "counts": counts,
            "has_more": total > len(items),
            "coverage": RESOURCE_COVERAGE,
        }

    if kind is None:
        # Explicit family paging avoids a misleading cross-domain cursor.
        kind = RESOURCE_KINDS[0]
    rows = list(families[kind][offset:offset + PAGE_SIZE + 1])
    page = rows[:PAGE_SIZE]
    return {
        "space_id": str(space.pk),
        "visibility": "visible",
        "kind": kind,
        "items": [_item(kind, row, slug=space.slug) for row in page],
        "count": counts[kind],
        "counts": counts,
        "total_count": total,
        "has_more": len(rows) > PAGE_SIZE,
        "next_offset": offset + len(page),
        "coverage": RESOURCE_COVERAGE,
    }
