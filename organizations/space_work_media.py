"""Owner-validated public recognition media for Creative and Media work.

PresentationMediaUse is a use of an owner asset, never a Production/Post.
Never return storage paths or treat a Space workspace viewer as authorized for
public delivery. The media delivery endpoint independently rechecks access.
"""
from __future__ import annotations

from django.urls import reverse

from activities.models import Activity, ActivityStatus, ActivityVisibility, Occurrence
from groups.selectors import eligible_activity_ids_for_profile
from organizations.models import SpaceArchetype, SpaceLifecycle
from presentations.media_selectors import public_presentation_media_for_activities


def attach_space_work_recognition_media(*, profile, space, sections):
    """Attach at most one genuine published recognition image per visible row.

    A workspace can contain private Activities and private assets. The only
    delivery available today is the *public* published-media-use endpoint:
    therefore we must pass every public delivery gate before emitting a URL.
    Media is optional and must never affect Activity/Occurrence status,
    sort order, WorkItem existence or owner authority.
    """
    if space.archetype not in {
        SpaceArchetype.CREATIVE, SpaceArchetype.MEDIA,
    } or not (
        space.public_profile
        and space.searchable
        and space.lifecycle == SpaceLifecycle.ACTIVE
        and space.verification_status != "suspended"
    ):
        return

    rows = [
        item
        for section in sections.values()
        for item in section["items"]
        if item.get("source", {}).get("kind") in {"activity", "occurrence"}
    ]
    activity_ids = set()
    occurrence_ids = set()
    for item in rows:
        source = item["source"]
        if source["kind"] == "activity":
            activity_ids.add(source["id"])
        elif source["kind"] == "occurrence":
            occurrence_ids.add(source["id"])
            activity_ids.add(item["context"]["activity"]["id"])
    if not activity_ids:
        return

    candidates = list(
        Activity.objects.filter(
            pk__in=activity_ids,
            space=space,
            visibility=ActivityVisibility.PUBLIC,
            status=ActivityStatus.PUBLISHED,
        )
    )
    eligible = set(eligible_activity_ids_for_profile(
        profile, [activity.pk for activity in candidates]
    ))
    candidates = [activity for activity in candidates if activity.pk in eligible]
    if not candidates:
        return
    allowed_ids = {str(activity.pk) for activity in candidates}
    occurrences = list(
        Occurrence.objects.filter(
            pk__in=occurrence_ids, activity_id__in=eligible
        )
    ) if occurrence_ids else []

    by_activity = public_presentation_media_for_activities(
        candidates, occurrences=occurrences,
    )
    for item in rows:
        source = item["source"]
        activity_id = (
            source["id"] if source["kind"] == "activity"
            else item["context"]["activity"]["id"]
        )
        if activity_id not in allowed_ids:
            continue
        # A media use attached to a specific Occurrence must not appear
        # on its parent Activity or on a different Occurrence.
        occurrence_id = (
            source["id"] if source["kind"] == "occurrence" else None
        )
        matching = [
            media for media in by_activity.get(activity_id, ())
            if media.mime_type in {"image/jpeg", "image/png"}
            and (media.occurrence_id is None
                 or media.occurrence_id == occurrence_id)
            and (occurrence_id is not None or media.occurrence_id is None)
        ]
        matching.sort(key=lambda media: (
            media.occurrence_id != occurrence_id,
            media.position, media.use_id,
        ))
        if not matching:
            continue
        media = matching[0]
        item["media_bindings"] = [{
            "resource_ref": f"presentation_media_use:{media.use_id}",
            "owner": source,
            "target": "subject",
            "purpose": "recognize",
            "kind": "image",
            "mime_type": media.mime_type,
            "label": media.alt_text,
            "url": reverse(
                "presentations:published-media-file",
                kwargs={"use_id": media.use_id},
            ),
            "authorized": True,
            "presentation_rank": "support",
        }]
