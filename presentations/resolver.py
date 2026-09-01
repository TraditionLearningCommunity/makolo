from dataclasses import dataclass

from .enums import PresentationState, VersionStatus
from .essential import ESSENTIAL_MANIFEST, ESSENTIAL_THEME
from .manifests.validation import validate_manifest
from .models import ActivityPresentation, PresentationTemplateVersion, PresentationThemeVersion


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


def _previous_healthy(binding, purpose):
    template_versions = PresentationTemplateVersion.objects.filter(
        template=binding.template_version.template,
        status=VersionStatus.PUBLISHED,
        version_number__lt=binding.template_version.version_number,
    ).order_by("-version_number")
    theme_versions = PresentationThemeVersion.objects.filter(
        theme=binding.theme_version.theme,
        status=VersionStatus.PUBLISHED,
        version_number__lte=binding.theme_version.version_number,
    ).order_by("-version_number")
    for template_version in template_versions:
        try:
            validate_manifest(template_version.manifest)
        except Exception:
            continue
        if purpose not in template_version.manifest.get("purposes", []):
            continue
        theme_version = theme_versions.first()
        if theme_version:
            return ResolvedPresentation(template_version.manifest, theme_version.tokens, binding, "previous-healthy-version")
    return None


def resolve_presentation(*, activity, purpose, occurrence=None):
    qs = ActivityPresentation.objects.select_related(
        "template_version",
        "template_version__template",
        "theme_version",
        "theme_version__theme",
    )
    candidates = []
    if occurrence is not None:
        candidates.append(qs.filter(activity=activity, occurrence=occurrence, purpose=purpose).first())
    candidates.append(qs.filter(activity=activity, occurrence__isnull=True, purpose=purpose).first())
    for binding in candidates:
        if _healthy(binding):
            return ResolvedPresentation(binding.template_version.manifest, binding.theme_version.tokens, binding)
        if binding:
            previous = _previous_healthy(binding, str(purpose))
            if previous:
                return previous
            if binding.template_version.status == VersionStatus.SUSPENDED or binding.theme_version.status == VersionStatus.SUSPENDED:
                break
    return ResolvedPresentation(ESSENTIAL_MANIFEST, ESSENTIAL_THEME, None, "makolo-essential")
