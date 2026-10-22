"""Public media delivery through the *published use*, never the raw asset URL."""
from django.http import FileResponse, Http404
from django.views.decorators.http import require_GET

from activities.models import ActivityStatus, ActivityVisibility
from accounts.models import UserProfile
from organizations.models import SpaceLifecycle
from groups.selectors import eligible_activity_ids_for_profile
from .media_models import PresentationMediaState, PresentationMediaUse


@require_GET
def published_media_file(request, use_id):
    use = (
        PresentationMediaUse.objects.select_related(
            "activity", "asset", "occurrence", "activity__space", "activity__owner_profile"
        ).filter(pk=use_id, state=PresentationMediaState.PUBLISHED).first()
    )
    if use is None:
        raise Http404
    activity = use.activity
    if activity.status != ActivityStatus.PUBLISHED or activity.visibility != ActivityVisibility.PUBLIC:
        raise Http404
    if activity.pk not in eligible_activity_ids_for_profile(request.user, [activity.pk]):
        raise Http404
    if activity.space_id:
        space = activity.space
        if not (
            space.public_profile and space.searchable
            and space.lifecycle == SpaceLifecycle.ACTIVE
            and space.verification_status != "suspended"
        ):
            raise Http404
    elif not UserProfile.objects.filter(
        user_id=activity.owner_profile_id,
        public_profile=True,
        searchable=True,
        user__is_active=True,
    ).exists():
        raise Http404
    # Publication of an association cannot transfer ownership of the underlying asset.
    if use.asset.owner_space_id:
        if use.asset.owner_space_id != activity.space_id:
            raise Http404
    elif use.asset.owner_profile_id:
        if activity.space_id or use.asset.owner_profile_id != activity.owner_profile_id:
            raise Http404
    else:
        raise Http404
    if use.occurrence_id and use.occurrence.activity_id != activity.pk:
        raise Http404
    if use.asset.mime_type not in {"image/jpeg", "image/png"}:
        raise Http404
    file = use.asset.file
    if not file or not file.storage.exists(file.name):
        raise Http404
    try:
        response = FileResponse(file.open("rb"), content_type=use.asset.mime_type)
    except (OSError, ValueError):
        raise Http404
    response["Cache-Control"] = "private, no-store, max-age=0"
    response["X-Content-Type-Options"] = "nosniff"
    return response
