from copy import deepcopy

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from authorization.constants import PermissionCode
from authorization.services import can

from .accessibility import validate_publication_accessibility
from .enums import Provenance, VersionStatus, Visibility
from .library_models import PresentationTemplateModeration, SpacePresentationDefault
from .manifests.validation import validate_manifest
from .models import PresentationTemplate, PresentationTemplateVersion, PresentationTheme, PresentationThemeVersion
from .themes import validate_theme_tokens


def _require_space_library(actor, space):
    if not getattr(actor, "is_authenticated", False) or not can(actor, PermissionCode.SPACE_MANAGE, space):
        raise PermissionDenied("Vous ne pouvez pas gérer la bibliothèque de cet Espace.")


def _require_platform_moderator(actor):
    if not getattr(actor, "is_authenticated", False):
        raise PermissionDenied("Autorité plateforme requise.")
    if not (getattr(actor, "is_staff", False) or can(actor, PermissionCode.PLATFORM_MANAGE)):
        raise PermissionDenied("Autorité plateforme requise.")


def _template_visible_for_space(version, space):
    return version.template.visibility == Visibility.PUBLIC or version.template.owner_space_id == space.pk


def _theme_visible_for_space(version, space):
    return version.theme.visibility == Visibility.PUBLIC or version.theme.owner_space_id == space.pk


def _template_selectable(actor, version, activity):
    template = version.template
    if template.visibility == Visibility.PUBLIC:
        return True
    if template.owner_profile_id == getattr(actor, "pk", None):
        return True
    return bool(template.owner_space_id and activity.space_id == template.owner_space_id and can(actor, PermissionCode.ACTIVITY_MANAGE, activity=activity))


def _theme_selectable(actor, version, activity):
    theme = version.theme
    if theme.visibility == Visibility.PUBLIC:
        return True
    if theme.owner_profile_id == getattr(actor, "pk", None):
        return True
    return bool(theme.owner_space_id and activity.space_id == theme.owner_space_id and can(actor, PermissionCode.ACTIVITY_MANAGE, activity=activity))


@transaction.atomic
def duplicate_template(*, actor, source_version, slug, name, owner_space=None):
    if source_version.status not in {VersionStatus.PUBLISHED, VersionStatus.RETIRED}:
        raise ValidationError("Seule une version sûre publiée ou retirée peut être dupliquée.")
    source = source_version.template
    if source.visibility != Visibility.PUBLIC and source.owner_profile_id != actor.pk and source.owner_space_id != getattr(owner_space, "pk", None):
        raise PermissionDenied("Ce modèle n’est pas accessible.")
    if owner_space is not None:
        _require_space_library(actor, owner_space)
        provenance, owner_profile = Provenance.SPACE, None
    else:
        provenance, owner_profile = Provenance.USER, actor
    template = PresentationTemplate.objects.create(slug=slug, name=name, description=source.description, provenance=provenance, visibility=Visibility.SPACE if owner_space else Visibility.PRIVATE, owner_profile=owner_profile, owner_space=owner_space, created_by=actor)
    version = PresentationTemplateVersion.objects.create(template=template, version_number=1, status=VersionStatus.DRAFT, schema_version=source_version.schema_version, manifest=deepcopy(source_version.manifest), created_by=actor)
    return template, version


@transaction.atomic
def duplicate_theme(*, actor, source_version, slug, name, owner_space=None):
    if source_version.status not in {VersionStatus.PUBLISHED, VersionStatus.RETIRED}:
        raise ValidationError("Seule une version sûre publiée ou retirée peut être dupliquée.")
    source = source_version.theme
    if source.visibility != Visibility.PUBLIC and source.owner_profile_id != actor.pk and source.owner_space_id != getattr(owner_space, "pk", None):
        raise PermissionDenied("Ce thème n’est pas accessible.")
    if owner_space is not None:
        _require_space_library(actor, owner_space)
        provenance, owner_profile = Provenance.SPACE, None
    else:
        provenance, owner_profile = Provenance.USER, actor
    theme = PresentationTheme.objects.create(slug=slug, name=name, provenance=provenance, visibility=Visibility.SPACE if owner_space else Visibility.PRIVATE, owner_profile=owner_profile, owner_space=owner_space, created_by=actor)
    version = PresentationThemeVersion.objects.create(theme=theme, version_number=1, status=VersionStatus.DRAFT, schema_version=source_version.schema_version, tokens=deepcopy(source_version.tokens), created_by=actor)
    return theme, version


@transaction.atomic
def set_space_default(*, actor, space, purpose, template_version, theme_version):
    _require_space_library(actor, space)
    if template_version.status != VersionStatus.PUBLISHED or theme_version.status != VersionStatus.PUBLISHED:
        raise ValidationError("Un default Espace exige des versions publiées.")
    if not _template_visible_for_space(template_version, space) or not _theme_visible_for_space(theme_version, space):
        raise PermissionDenied("Un default Espace ne peut pas référencer une ressource privée d’un autre propriétaire.")
    default, _ = SpacePresentationDefault.objects.update_or_create(space=space, purpose=purpose, defaults={"template_version": template_version, "theme_version": theme_version, "updated_by": actor})
    return default


@transaction.atomic
def upgrade_presentation(*, actor, presentation, template_version=None, theme_version=None):
    from .services import ensure_activity_presentation_authority
    presentation = presentation.__class__.objects.select_for_update().select_related("activity", "template_version", "theme_version").get(pk=presentation.pk)
    ensure_activity_presentation_authority(actor, presentation.activity)
    next_template = template_version or presentation.template_version
    next_theme = theme_version or presentation.theme_version
    if next_template.status != VersionStatus.PUBLISHED or next_theme.status != VersionStatus.PUBLISHED:
        raise ValidationError("Une mise à jour exige des versions publiées.")
    if not _template_selectable(actor, next_template, presentation.activity) or not _theme_selectable(actor, next_theme, presentation.activity):
        raise PermissionDenied("La nouvelle version n’est pas accessible dans cette Activity.")
    validate_manifest(next_template.manifest)
    validate_theme_tokens(next_theme.tokens)
    if presentation.purpose not in next_template.manifest.get("purposes", []):
        raise ValidationError("La nouvelle version n’est pas compatible avec cet usage.")
    presentation.template_version = next_template
    presentation.theme_version = next_theme
    presentation.save(update_fields=["template_version", "theme_version", "updated_at"])
    return presentation


@transaction.atomic
def submit_template_version(*, actor, version):
    if version.template.owner_profile_id != actor.pk and version.template.owner_space_id is None:
        raise PermissionDenied("Vous ne pouvez pas soumettre ce modèle.")
    if version.template.owner_space_id is not None:
        _require_space_library(actor, version.template.owner_space)
    validate_manifest(version.manifest)
    version.status = VersionStatus.SUBMITTED
    version.save(update_fields=["status"])
    moderation, _ = PresentationTemplateModeration.objects.update_or_create(version=version, defaults={"submitted_by": actor, "reviewed_by": None, "reviewed_at": None, "decision_note": ""})
    return moderation


@transaction.atomic
def publish_template_version(*, actor, version, note=""):
    _require_platform_moderator(actor)
    if version.status != VersionStatus.SUBMITTED:
        raise ValidationError("Seule une contribution soumise peut être publiée globalement.")
    validate_manifest(version.manifest)
    validate_publication_accessibility(version.manifest)
    moderation = PresentationTemplateModeration.objects.select_for_update().get(version=version)
    version.status = VersionStatus.PUBLISHED
    version.template.visibility = Visibility.PUBLIC
    version.template.save(update_fields=["visibility", "updated_at"])
    version.save(update_fields=["status", "published_at"])
    moderation.reviewed_by = actor
    moderation.reviewed_at = timezone.now()
    moderation.decision_note = (note or "").strip()
    moderation.save(update_fields=["reviewed_by", "reviewed_at", "decision_note"])
    return version


@transaction.atomic
def suspend_template_version(*, actor, version, note=""):
    _require_platform_moderator(actor)
    version.status = VersionStatus.SUSPENDED
    version.save(update_fields=["status"])
    moderation = PresentationTemplateModeration.objects.filter(version=version).first()
    if moderation:
        moderation.reviewed_by = actor
        moderation.reviewed_at = timezone.now()
        moderation.decision_note = (note or "").strip()
        moderation.save(update_fields=["reviewed_by", "reviewed_at", "decision_note"])
    return version


@transaction.atomic
def retire_template_version(*, actor, version):
    if version.template.owner_profile_id == actor.pk:
        pass
    elif version.template.owner_space_id is not None:
        _require_space_library(actor, version.template.owner_space)
    else:
        _require_platform_moderator(actor)
    version.status = VersionStatus.RETIRED
    version.save(update_fields=["status"])
    return version
