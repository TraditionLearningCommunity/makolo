"""Deliver only a currently published PresentationMediaUse, never its raw asset URL."""
from django.http import FileResponse, Http404
from django.urls import reverse
from django.views.decorators.http import require_GET

from activities.models import OccurrenceStatus
from authorization.constants import PermissionCode
from authorization.services import can
from core.participant_selectors import (
    participant_accesses_visible_to_buyer, participant_journeys,
)
from groups.selectors import eligible_activity_ids_for_profile
from journeys.models import WorkflowKind
from .asset_models import PresentationAsset
from .enums import PresentationPurpose, PresentationState
from .media_models import PresentationMediaState, PresentationMediaUse
from .media_selectors import public_media_activities
from .models import ActivityPresentation


@require_GET
def published_media_file(request, use_id):
    use = (
        PresentationMediaUse.objects.select_related(
            "activity", "asset", "occurrence", "activity__space",
            "activity__owner_profile",
        ).filter(pk=use_id, state=PresentationMediaState.PUBLISHED).first()
    )
    if use is None:
        raise Http404
    activity = use.activity
    # Same gate used at projection time; a cached link cannot bypass an
    # Activity's newly retired owner, privacy change or suspended Space.
    if not public_media_activities(activity_ids=[activity.pk]).exists():
        raise Http404
    if activity.pk not in eligible_activity_ids_for_profile(request.user, [activity.pk]):
        raise Http404
    if use.occurrence_id and (
        use.occurrence.activity_id != activity.pk
        or use.occurrence.status != OccurrenceStatus.SCHEDULED
    ):
        raise Http404
    # The media-use relation does not transfer asset ownership.
    if use.asset.owner_space_id:
        if use.asset.owner_space_id != activity.space_id:
            raise Http404
    elif use.asset.owner_profile_id:
        if activity.space_id or use.asset.owner_profile_id != activity.owner_profile_id:
            raise Http404
    else:
        raise Http404
    if use.asset.mime_type not in {"image/jpeg", "image/png"}:
        raise Http404
    file = use.asset.private_file if use.asset.private_file else use.asset.file
    if not file:
        raise Http404
    try:
        if not file.storage.exists(file.name):
            raise Http404
        stream = file.open("rb")
    except (OSError, ValueError):
        raise Http404 from None
    response = FileResponse(stream, content_type=use.asset.mime_type)
    response["Content-Disposition"] = "inline"
    response["Cache-Control"] = "private, no-store, max-age=0"
    response["X-Content-Type-Options"] = "nosniff"
    response["Cross-Origin-Resource-Policy"] = "same-site"
    return response



@require_GET
def editorial_media_file(request, asset_id):
    """Resolve new protected MPS hero images through their actual presentation.

    A draft is available only to its authorized editor. A published image is
    visible only where the existing Presentation owner/recipient is authorized.
    This is NOT a generic public asset URL and never accesses legacy file URLs.
    """
    asset = PresentationAsset.objects.filter(pk=asset_id).first()
    if asset is None or not asset.private_file or asset.mime_type not in {
        "image/png", "image/jpeg",
    }:
        raise Http404
    link = reverse("presentations:editorial-media-file", kwargs={"asset_id": asset.pk})
    bindings = ActivityPresentation.objects.filter(
        editorial_data__hero_image=link,
    ).select_related("activity", "activity__space", "activity__owner_profile")
    authorized = False
    for binding in bindings:
        activity = binding.activity
        if asset.owner_space_id:
            if asset.owner_space_id != activity.space_id:
                continue
        elif asset.owner_profile_id:
            if activity.space_id or asset.owner_profile_id != activity.owner_profile_id:
                continue
        else:
            continue
        viewer = request.user
        if getattr(viewer, "is_authenticated", False) and can(
            viewer, PermissionCode.ACTIVITY_MANAGE, activity=activity,
        ):
            authorized = True
            break
        if binding.state != PresentationState.PUBLISHED:
            continue
        if binding.purpose in {
            PresentationPurpose.PUBLIC_PAGE, PresentationPurpose.PROGRAM,
        }:
            if (
                public_media_activities(activity_ids=[activity.pk]).exists()
                and activity.pk in eligible_activity_ids_for_profile(
                    viewer, [activity.pk],
                )
            ):
                authorized = True
                break
        elif getattr(viewer, "is_authenticated", False):
            if binding.purpose == PresentationPurpose.INVITATION:
                authorized = participant_journeys(viewer).filter(
                    activity_id=activity.pk, workflow=WorkflowKind.INVITATION,
                ).exists()
            elif binding.purpose == PresentationPurpose.ACCESS_PASS:
                authorized = participant_accesses_visible_to_buyer(viewer).filter(
                    journey__activity_id=activity.pk,
                ).exists()
            if authorized:
                break
    if not authorized:
        raise Http404
    try:
        if not asset.private_file.storage.exists(asset.private_file.name):
            raise Http404
        stream = asset.private_file.open("rb")
    except (OSError, ValueError):
        raise Http404 from None
    response = FileResponse(stream, content_type=asset.mime_type)
    response["Content-Disposition"] = "inline"
    response["Cache-Control"] = "private, no-store, max-age=0"
    response["X-Content-Type-Options"] = "nosniff"
    response["Cross-Origin-Resource-Policy"] = "same-site"
    return response
