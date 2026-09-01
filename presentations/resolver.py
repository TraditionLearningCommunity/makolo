from dataclasses import dataclass

from .enums import PresentationState, VersionStatus
from .essential import ESSENTIAL_MANIFEST, ESSENTIAL_THEME
from .models import ActivityPresentation


@dataclass(frozen=True)
class ResolvedPresentation:
    manifest: dict
    theme_tokens: dict
    binding: ActivityPresentation | None
    fallback_reason: str = ""


def _healthy(binding):
    return (
        binding
        and binding.state == PresentationState.PUBLISHED
        and binding.template_version.status == VersionStatus.PUBLISHED
        and binding.theme_version.status == VersionStatus.PUBLISHED
    )


def resolve_presentation(*, activity, purpose, occurrence=None):
    qs = ActivityPresentation.objects.select_related("template_version", "theme_version")
    candidates = []
    if occurrence is not None:
        candidates.append(qs.filter(activity=activity, occurrence=occurrence, purpose=purpose).first())
    candidates.append(qs.filter(activity=activity, occurrence__isnull=True, purpose=purpose).first())
    for binding in candidates:
        if _healthy(binding):
            return ResolvedPresentation(binding.template_version.manifest, binding.theme_version.tokens, binding)
        if binding and (
            binding.template_version.status == VersionStatus.SUSPENDED
            or binding.theme_version.status == VersionStatus.SUSPENDED
        ):
            break
    return ResolvedPresentation(ESSENTIAL_MANIFEST, ESSENTIAL_THEME, None, "makolo-essential")
