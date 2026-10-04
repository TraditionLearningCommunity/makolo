from django.db.models import Q

from .enums import VersionStatus, Visibility
from .models import PresentationTemplateVersion, PresentationThemeVersion


def available_template_versions(*, actor, activity, purpose):
    ownership = Q(template__visibility=Visibility.PUBLIC) | Q(template__owner_profile=actor)
    if activity.space_id:
        ownership |= Q(template__owner_space_id=activity.space_id)
    versions = (
        PresentationTemplateVersion.objects.filter(status=VersionStatus.PUBLISHED)
        .filter(ownership)
        .select_related("template")
        .order_by("template__name", "-version_number")
        .distinct()
    )
    return [
        version
        for version in versions
        if purpose in version.manifest.get("purposes", [])
    ]


def available_theme_versions(*, actor, activity):
    ownership = Q(theme__visibility=Visibility.PUBLIC) | Q(theme__owner_profile=actor)
    if activity.space_id:
        ownership |= Q(theme__owner_space_id=activity.space_id)
    return list(
        PresentationThemeVersion.objects.filter(status=VersionStatus.PUBLISHED)
        .filter(ownership)
        .select_related("theme")
        .order_by("theme__name", "-version_number")
        .distinct()
    )
