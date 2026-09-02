from .models import PersonalAsset, PersonalAssetVersion


def personal_assets_for_controller(profile, *, include_archived=False):
    queryset = PersonalAsset.objects.filter(controller=profile)
    if not include_archived:
        queryset = queryset.filter(archived_at__isnull=True)
    return queryset.select_related("subject_profile", "subject_external_beneficiary")


def personal_asset_for_controller(profile, asset_id, *, include_archived=False):
    return personal_assets_for_controller(profile, include_archived=include_archived).get(pk=asset_id)


def personal_asset_versions_for_controller(profile, asset):
    return PersonalAssetVersion.objects.filter(asset=asset, asset__controller=profile).order_by("version", "created_at")
