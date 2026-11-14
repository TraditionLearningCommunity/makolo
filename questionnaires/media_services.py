"""Canonical questionnaire media: authoring permissions and private delivery."""
from pathlib import Path
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Q
from authorization.constants import PermissionCode
from authorization.services import can
from .models import (
    FormVersion, FormVersionStatus, FormQuestion, FormRequest, FormRequestStatus, QuestionnaireMedia,
    QuestionType,
)
from journeys.collaboration_services import validate_artifact_upload
from core.private_media_validation import validate_recorded_media, ensure_media_kind


def _can_manage(actor, version):
    return bool(getattr(actor, "is_authenticated", False) and
                can(actor, PermissionCode.ACTIVITY_MANAGE, activity=version.form.activity))


def ensure_media_access(actor, media):
    if not getattr(actor, "is_authenticated", False):
        raise PermissionDenied("Connexion requise.")
    if _can_manage(actor, media.form_version):
        return
    if not FormRequest.objects.filter(
        form_version=media.form_version,
    ).exclude(status=FormRequestStatus.CANCELLED).filter(
        Q(target_profile=actor) | Q(journey__beneficiary=actor)
    ).exists():
        raise PermissionDenied("Média de questionnaire inaccessible.")


def serialize_media(media):
    return {
        "id": str(media.pk),
        "kind": media.kind,
        "name": media.original_name,
        "caption": media.caption,
        "position": media.position,
        "mime_type": media.mime_type,
        "size": media.size,
        "download_path": f"api/v1/questionnaires/media/{media.pk}/download/",
    }


@transaction.atomic
def add_questionnaire_media(
    *, actor, version, uploaded_file, kind, caption="", position=0,
    question=None, choice_index=None,
):
    version = FormVersion.objects.select_for_update().select_related(
        "form__activity",
    ).get(pk=version.pk)
    if not _can_manage(actor, version):
        raise PermissionDenied("Vous ne pouvez pas enrichir ce questionnaire.")
    if version.status != FormVersionStatus.DRAFT:
        raise ValidationError("Créez une nouvelle version pour enrichir un formulaire publié.")
    if question is not None:
        question = FormQuestion.objects.get(pk=question.pk)
        if question.form_version_id != version.pk:
            raise ValidationError({"question": "Question étrangère à la version."})
    if choice_index is not None:
        if (question is None or question.question_type not in {
            QuestionType.SINGLE_CHOICE, QuestionType.MULTIPLE_CHOICE,
        } or isinstance(choice_index, bool) or not isinstance(choice_index, int)
                or choice_index < 0 or choice_index >= len(question.choices)):
            raise ValidationError({"choice_index": "Choix de question invalide."})
    if kind not in {"image", "video", "audio", "voice", "file"}:
        raise ValidationError({"kind": "Type de média invalide."})
    caption = (caption or "").strip()
    if len(caption) > 5000:
        raise ValidationError({"caption": "Légende trop longue."})
    if not isinstance(position, int) or position < 0 or position > 100000:
        raise ValidationError({"position": "Position invalide."})
    if kind == "file" or kind == "image":
        data, mime, digest = validate_artifact_upload(uploaded_file)
    else:
        data, mime, digest = validate_recorded_media(uploaded_file, kind)
    ensure_media_kind(kind, mime)
    media = QuestionnaireMedia(
        form_version=version, question=question, choice_index=choice_index,
        caption=caption, position=position, kind=kind,
        original_name=Path(getattr(uploaded_file, "name", "fichier")).name,
        mime_type=mime, size=len(data), content_hash=digest,
        uploaded_by=actor,
    )
    media.file.save("payload.bin", ContentFile(data), save=False)
    try:
        media.save()
    except Exception:
        if media.file.name:
            media.file.storage.delete(media.file.name)
        raise
    return media



@transaction.atomic
def remove_questionnaire_media(*, actor, media):
    """Remove an incorrect draft attachment without changing published data."""
    version = FormVersion.objects.select_for_update().select_related(
        "form__activity",
    ).get(pk=media.form_version_id)
    if not _can_manage(actor, version):
        raise PermissionDenied("Vous ne pouvez pas retirer ce média.")
    if version.status != FormVersionStatus.DRAFT:
        raise ValidationError("Les médias d'une version publiée sont immuables.")
    locked = QuestionnaireMedia.objects.select_for_update().get(pk=media.pk)
    name = locked.file.name
    storage = locked.file.storage
    locked.delete()
    if name:
        transaction.on_commit(lambda: storage.delete(name))


def media_sections(version):
    """Build bounded, ordered media relations without mutating JSON choices."""
    media = list(version.media.all().order_by("position", "created_at", "pk"))
    root = [item for item in media if item.question_id is None]
    by_question, by_choice = {}, {}
    for item in media:
        if item.question_id:
            if item.choice_index is None:
                by_question.setdefault(item.question_id, []).append(item)
            else:
                by_choice.setdefault((item.question_id, item.choice_index), []).append(item)
    return root, by_question, by_choice
