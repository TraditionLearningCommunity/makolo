"""Reuse existing, authorized images across demo Activity/Occurrence contexts.

No file is copied and no owner is changed. The canonical Presentation services
must approve the association and its publication. --apply is required to write.
"""
import argparse
from collections import Counter


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--count", type=int, default=50, help="Maximum new media uses")
    p.add_argument("--per-asset", type=int, default=3, help="Maximum new uses of one asset")
    p.add_argument("--apply", action="store_true")
    a = p.parse_args(argv)
    if not 1 <= a.count <= 10000 or not 1 <= a.per_asset <= 10:
        p.error("Expected count 1..10000 and per-asset 1..10")
    import django
    django.setup()
    from django.core.exceptions import PermissionDenied, ValidationError
    from django.db import connection, transaction
    from django.db.models import Q
    from activities.models import Activity, ActivityStatus
    from authorization.constants import PermissionCode
    from authorization.services import can
    from presentations.models import PresentationAsset, PresentationMediaUse
    from presentations.media_models import PresentationMediaPurpose, PresentationMediaState
    from presentations.media_services import associate_presentation_media, publish_presentation_media
    if connection.vendor != "sqlite":
        p.error("Demo media generation is limited to SQLite")

    counts = Counter()
    candidates = PresentationAsset.objects.filter(
        Q(owner_profile__isnull=False) | Q(owner_space__isnull=False),
        mime_type__in=("image/jpeg", "image/png"),
    ).select_related("owner_profile", "owner_space", "uploaded_by").order_by("id")
    for asset in candidates:
        if counts["new"] + counts["planned"] >= a.count:
            break
        actor = asset.owner_profile if asset.owner_profile_id else asset.uploaded_by
        if actor is None or not actor.is_active:
            counts["actor_unavailable"] += 1
            continue
        stored = asset.private_file if asset.private_file else asset.file
        if not stored:
            counts["file_absent"] += 1
            continue
        # Do not write a broken media use into the DB. The same check is enforced
        # again during publication by the production service.
        if not stored.storage.exists(stored.name):
            counts["file_absent"] += 1
            continue
        activities = Activity.objects.filter(
            slug__startswith="demo-", status=ActivityStatus.PUBLISHED
        )
        if asset.owner_profile_id:
            activities = activities.filter(
                owner_profile_id=asset.owner_profile_id, space__isnull=True
            )
        else:
            activities = activities.filter(space_id=asset.owner_space_id)
        uses_for_asset = 0
        for activity in activities.order_by("id")[: max(a.per_asset * 8, 12)]:
            if uses_for_asset >= a.per_asset or counts["new"] + counts["planned"] >= a.count:
                break
            if not can(actor, PermissionCode.ACTIVITY_MANAGE, activity=activity):
                counts["no_activity_authority"] += 1
                continue
            # For Space-owned assets the uploader must additionally be authorized
            # to use assets of that Space; no implicit transfer of asset rights.
            if asset.owner_space_id and not can(
                actor, PermissionCode.SPACE_MANAGE, space=activity.space
            ):
                counts["no_asset_authority"] += 1
                continue
            existing = PresentationMediaUse.objects.filter(
                activity=activity, occurrence__isnull=True, asset=asset,
                purpose=PresentationMediaPurpose.RECOGNIZE,
            ).exclude(state=PresentationMediaState.RETIRED).order_by("id").first()
            if existing and existing.state == PresentationMediaState.PUBLISHED:
                counts["existing_published"] += 1
                continue
            if not a.apply:
                counts["planned"] += 1
                uses_for_asset += 1
                continue
            try:
                source_use = PresentationMediaUse.objects.filter(
                    asset=asset, state=PresentationMediaState.PUBLISHED,
                ).exclude(alt_text="").order_by("id").first()
                alt_text = (source_use.alt_text if source_use else
                    "Illustration de demonstration pour " + activity.title[:200])
                with transaction.atomic():
                    use = existing or associate_presentation_media(
                        actor=actor, activity=activity, asset=asset,
                        purpose=PresentationMediaPurpose.RECOGNIZE,
                        alt_text=alt_text,
                    )
                    publish_presentation_media(actor=actor, media_use=use)
                counts["new"] += 1
                uses_for_asset += 1
            except (ValidationError, PermissionDenied, OSError):
                counts["rejected"] += 1
    print("MEDIA", "APPLY" if a.apply else "PREVIEW", dict(sorted(counts.items())))
    print("No file copy, no ownership change, no external asset authorization bypass.")


if __name__ == "__main__":
    main()
