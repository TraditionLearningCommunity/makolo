"""Privacy-scoped, URL-free media projection candidates for P3."""
from dataclasses import dataclass

from activities.models import ActivityStatus, ActivityVisibility

from .media_models import PresentationMediaPurpose, PresentationMediaState, PresentationMediaUse


@dataclass(frozen=True)
class ResolvedPresentationMedia:
    use_id: str
    asset_id: str
    activity_id: str
    occurrence_id: str | None
    purpose: str
    mime_type: str
    alt_text: str
    position: int


def public_presentation_media_for_activities(activities, *, occurrences=(), purpose=PresentationMediaPurpose.RECOGNIZE):
    """Return authorized uses grouped by Activity ID without N+1 queries.

    This selector returns asset identity, never a raw storage URL. Asset delivery
    is subject to its own permission-checked transport in the consumer phase.
    """
    activities = list(activities)
    occurrences = list(occurrences)
    ids = {a.pk for a in activities if a.visibility == ActivityVisibility.PUBLIC and a.status == ActivityStatus.PUBLISHED}
    allowed_occurrence_ids = {o.pk for o in occurrences if o.activity_id in ids}
    result = {str(pk): [] for pk in ids}
    if not ids:
        return result
    qs = (
        PresentationMediaUse.objects.filter(
            activity_id__in=ids, state=PresentationMediaState.PUBLISHED, purpose=purpose,
        )
        .select_related("asset")
        .order_by("position", "created_at", "pk")
    )
    for use in qs:
        if use.occurrence_id is not None and use.occurrence_id not in allowed_occurrence_ids:
            continue
        result[str(use.activity_id)].append(
            ResolvedPresentationMedia(
                use_id=str(use.pk),
                asset_id=str(use.asset_id),
                activity_id=str(use.activity_id),
                occurrence_id=str(use.occurrence_id) if use.occurrence_id else None,
                purpose=use.purpose,
                mime_type=use.asset.mime_type,
                alt_text=use.alt_text,
                position=use.position,
            )
        )
    return result
