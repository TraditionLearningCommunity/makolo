"""Owner-scoped, URL-free media-use references for Discovery and Presentation.

The selector never grants media authority from a URL or an asset alone.
Delivery repeats the owner/group checks at request time.
"""
from dataclasses import dataclass

from django.db.models import Q

from activities.models import Activity, ActivityStatus, ActivityVisibility, OccurrenceStatus
from groups.selectors import eligible_activity_ids_for_profile
from organizations.models import SpaceLifecycle

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


def public_media_activities(*, activity_ids):
    """Query the logical owners, not an uploader or an asset's provenance.

    Unlike general Activity search, publishing a media file is also subject to
    the Space/Personal Profile's explicit public identity choice.
    """
    return (
        Activity.objects.filter(
            pk__in=activity_ids,
            status=ActivityStatus.PUBLISHED,
            visibility=ActivityVisibility.PUBLIC,
        )
        .filter(
            Q(
                space__isnull=False,
                space__public_profile=True,
                space__searchable=True,
                space__lifecycle=SpaceLifecycle.ACTIVE,
            )
            | Q(
                space__isnull=True,
                owner_profile__is_active=True,
                owner_profile__profile__public_profile=True,
                owner_profile__profile__searchable=True,
            )
        )
        .exclude(space__verification_status="suspended")
    )


def public_presentation_media_for_activities(
    activities, *, occurrences=(), purpose=PresentationMediaPurpose.RECOGNIZE, profile=None,
):
    """Return authorized, published, deliverable uses grouped by Activity ID.

    This returns neither storage locations nor raw asset URLs. An Activity
    owner can publish an association without making its underlying file
    publicly deliverable unless the Activity and Profile/Space are public.
    """
    activities = list(activities)
    occurrences = list(occurrences)
    proposed = {
        activity.pk for activity in activities
        if activity.visibility == ActivityVisibility.PUBLIC
        and activity.status == ActivityStatus.PUBLISHED
    }
    if not proposed:
        return {}
    admitted = set(
        public_media_activities(activity_ids=proposed).values_list("pk", flat=True)
    )
    admitted &= eligible_activity_ids_for_profile(profile, admitted)
    allowed_occurrences = {
        occurrence.pk for occurrence in occurrences
        if occurrence.activity_id in admitted
        and occurrence.status == OccurrenceStatus.SCHEDULED
    }
    result = {str(pk): [] for pk in admitted}
    if not admitted:
        return result

    uses = (
        PresentationMediaUse.objects.filter(
            activity_id__in=admitted,
            state=PresentationMediaState.PUBLISHED,
            purpose=purpose,
            asset__mime_type__in=("image/jpeg", "image/png"),
        )
        .filter(Q(asset__private_file__isnull=False) | ~Q(asset__file=""))
        .select_related("asset")
        .order_by("position", "created_at", "pk")
    )
    for use in uses:
        if use.occurrence_id is not None and use.occurrence_id not in allowed_occurrences:
            continue
        if use.asset.owner_space_id:
            if use.asset.owner_space_id not in {
                activity.space_id for activity in activities
                if activity.pk == use.activity_id
            }:
                continue
        elif use.asset.owner_profile_id:
            if use.asset.owner_profile_id not in {
                activity.owner_profile_id for activity in activities
                if activity.pk == use.activity_id and activity.space_id is None
            }:
                continue
        else:
            continue
        if not (use.asset.private_file or use.asset.file):
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
