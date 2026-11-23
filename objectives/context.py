"""Explicit presentation scope for Objectives; never an authority grant.

The authenticated human remains request.user. A Space lens only narrows
already-authorized Projects and Dossiers, and cannot select another Profile.
Omitting the lens preserves the existing cross-context personal organizer.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from urllib.parse import quote

from rest_framework.exceptions import ValidationError


_SPACE_SLUG = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$")


@dataclass(frozen=True)
class ObjectiveContext:
    kind: str = "personal"
    space_slug: str | None = None

    def filter(self, queryset):
        if self.kind == "space":
            return queryset.filter(owning_space__slug=self.space_slug)
        return queryset

    def describe(self, resource=None):
        if self.kind != "space":
            return {"kind": "personal"}
        space = getattr(resource, "owning_space", None)
        return {
            "kind": "space",
            "space": {
                "slug": self.space_slug,
                **({"id": str(space.pk)} if space is not None
                   and space.slug == self.space_slug else {}),
            },
        }

    def query_suffix(self):
        if self.kind != "space":
            return ""
        return "?context=space&space=" + quote(self.space_slug, safe="")


def resolve_objective_context(params):
    """Parse a scope hint, never a client-supplied actor or permission."""
    if any(key in params for key in ("profile_id", "viewer_id", "actor_id")):
        raise ValidationError({"context": "Le Profil agissant vient de la session."})
    if hasattr(params, "getlist") and any(
        len(params.getlist(key)) > 1 for key in ("context", "space")
    ):
        raise ValidationError({"context": "Contexte ambigu."})
    kind = params.get("context")
    space = params.get("space")
    if kind in (None, "personal") and space is None:
        return ObjectiveContext()
    if kind == "space" and isinstance(space, str) and _SPACE_SLUG.fullmatch(space):
        return ObjectiveContext(kind="space", space_slug=space)
    raise ValidationError({"context": "Utilisez personal ou space avec un slug Espace."})
