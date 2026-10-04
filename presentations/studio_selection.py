from django.db.models import Q

from .enums import Provenance, VersionStatus, Visibility
from .models import PresentationTemplateVersion, PresentationThemeVersion


def _scope_q(*, actor, activity, prefix):
    query = Q(**{f"{prefix}__visibility": Visibility.PUBLIC}) | Q(
        **{f"{prefix}__owner_profile": actor}
    )
    if activity.space_id:
        query |= Q(**{f"{prefix}__owner_space_id": activity.space_id})
    return query


def _source_label(*, item, actor, activity):
    owner = item.template if hasattr(item, "template") else item.theme
    if owner.provenance == Provenance.MAKOLO:
        return "Makolo"
    if owner.owner_profile_id == getattr(actor, "pk", None):
        return "Mes modèles"
    if activity.space_id and owner.owner_space_id == activity.space_id:
        return "Espace"
    return "Communauté"


def template_choices_for_activity(*, actor, activity, purpose):
    versions = (
        PresentationTemplateVersion.objects.filter(status=VersionStatus.PUBLISHED)
        .filter(_scope_q(actor=actor, activity=activity, prefix="template"))
        .select_related("template")
        .order_by("template__name", "-version_number")
    )
    result = []
    seen = set()
    for version in versions:
        if str(purpose) not in version.manifest.get("purposes", []):
            continue
        if version.template_id in seen:
            continue
        seen.add(version.template_id)
        result.append(
            {
                "version": version,
                "source": _source_label(item=version, actor=actor, activity=activity),
            }
        )
    return result


def theme_choices_for_activity(*, actor, activity):
    versions = (
        PresentationThemeVersion.objects.filter(status=VersionStatus.PUBLISHED)
        .filter(_scope_q(actor=actor, activity=activity, prefix="theme"))
        .select_related("theme")
        .order_by("theme__name", "-version_number")
    )
    result = []
    seen = set()
    for version in versions:
        if version.theme_id in seen:
            continue
        seen.add(version.theme_id)
        result.append(
            {
                "version": version,
                "source": _source_label(item=version, actor=actor, activity=activity),
            }
        )
    return result
