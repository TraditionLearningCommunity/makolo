"""Deliver only a currently published PresentationMediaUse, never its raw asset URL."""
from django.http import FileResponse, Http404
from django.views.decorators.http import require_GET

from activities.models import OccurrenceStatus
from groups.selectors import eligible_activity_ids_for_profile
from .media_models import PresentationMediaState, PresentationMediaUse
from .media_selectors import public_media_activities


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
