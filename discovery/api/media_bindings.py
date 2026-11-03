"""Pure Discovery composition of Presentation-owned media-use references.

The caller has already run the canonical admission and batch Presentation selector.
This module does not own files, publication or permissions.
"""
from django.urls import reverse


def apply_recognition_media(projection, media_uses, *, occurrence_id=None):
    """Mutate a finalized projection from a bounded authorized media-use collection."""
    admissible = [
        media for media in media_uses
        if media.occurrence_id is None or media.occurrence_id == occurrence_id
    ]
    if occurrence_id is not None:
        admissible.sort(key=lambda media: (
            media.occurrence_id != occurrence_id,
            media.position,
            media.use_id,
        ))
    admissible = admissible[:6]
    explicit = [
        {
            "resource": {
                "kind": "presentation_media_use",
                "id": media.use_id,
                "url": reverse("presentations:published-media-file", kwargs={"use_id": media.use_id}),
                "mime_type": media.mime_type,
                "alt_text": media.alt_text,
            },
            "target": dict(projection["identity"]["resource"]),
            "purpose": "RECOGNIZE",
        }
        for media in admissible
    ]
    if not explicit:
        return projection
    urls = {binding["resource"]["url"] for binding in explicit}
    projection["media_bindings"] = [
        *explicit,
        *[
            binding for binding in projection.get("media_bindings", [])
            if binding["resource"].get("url") not in urls
        ],
    ]
    projection["representation"]["image_url"] = explicit[0]["resource"]["url"]
    projection["representation"]["kind"] = "image"
    return projection
