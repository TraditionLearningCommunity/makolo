from dataclasses import dataclass

from .enums import PresentationState, VersionStatus
from .essential import ESSENTIAL_MANIFEST, ESSENTIAL_THEME
from .manifests.validation import validate_manifest
from .models import ActivityPresentation, PresentationTemplateVersion, PresentationThemeVersion

SAFE_PINNED_STATUSES = {VersionStatus.PUBLISHED, VersionStatus.RETIRED}


@dataclass(frozen=True)
class ResolvedPresentation:
    manifest: dict
    theme_tokens: dict
    binding: ActivityPresentation | None
    fallback_reason: str = ""


def _versions_safe(template_version, theme_version):
    return template_version.status in SAFE_PINNED_STATUSES and theme_version.status in SAFE_PINNED_STATUSES


def _healthy(binding):
    return binding and binding.state == PresentationState.PUBLISHED and _versions_safe(binding.template_version, binding.theme_version)


def _latest_safe_template(version, purpose):
    candidates = PresentationTemplateVersion.objects.filter(template=version.template, status=VersionStatus.PUBLISHED, version_number__lt=version.version_number).order_by("-version_number")
    for candidate in candidates:
        try:
            validate_manifest(candidate.manifest)
        except Exception:
            continue
        if purpose in candidate.manifest.get("purposes", []):
            return candidate
    return None


def _latest_safe_theme(version):
    return PresentationThemeVersion.objects.filter(theme=version.theme, status=VersionStatus.PUBLISHED, version_number__lt=version.version_number).order_by("-version_number").first()


def _security_fallback(binding, purpose):
    template = binding.template_version
    theme = binding.theme_version
    if template.status == VersionStatus.SUSPENDED:
        template = _latest_safe_template(template, purpose)
    if theme.status == VersionStatus.SUSPENDED:
        theme = _latest_safe_theme(theme)
    if template and theme and _versions_safe(template, theme):
        return ResolvedPresentation(template.manifest, theme.tokens, binding, "previous-healthy-version")
    return None


def _space_default(activity, purpose):
    if not activity.space_id:
        return None
    from .library_models import SpacePresentationDefault
    default = SpacePresentationDefault.objects.select_related("template_version", "theme_version").filter(space_id=activity.space_id, purpose=purpose).first()
    if default and _versions_safe(default.template_version, default.theme_version):
        return ResolvedPresentation(default.template_version.manifest, default.theme_version.tokens, None, "space-default")
    if default:
        class DefaultBinding:
            template_version = default.template_version
            theme_version = default.theme_version
        return _security_fallback(DefaultBinding(), str(purpose))
    return None


def resolve_presentation(*, activity, purpose, occurrence=None):
    qs = ActivityPresentation.objects.select_related("template_version", "template_version__template", "theme_version", "theme_version__theme")
    candidates = []
    if occurrence is not None:
        candidates.append(qs.filter(activity=activity, occurrence=occurrence, purpose=purpose).first())
    candidates.append(qs.filter(activity=activity, occurrence__isnull=True, purpose=purpose).first())
    for binding in candidates:
        if _healthy(binding):
            return ResolvedPresentation(binding.template_version.manifest, binding.theme_version.tokens, binding)
        if binding and (binding.template_version.status == VersionStatus.SUSPENDED or binding.theme_version.status == VersionStatus.SUSPENDED):
            safe = _security_fallback(binding, str(purpose))
            if safe:
                return safe
            break
    default = _space_default(activity, purpose)
    if default:
        return default
    return ResolvedPresentation(ESSENTIAL_MANIFEST, ESSENTIAL_THEME, None, "makolo-essential")
