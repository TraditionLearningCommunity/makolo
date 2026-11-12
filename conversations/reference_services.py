"""Typed links recheck the target owner's ACL at publication AND acquisition."""
from uuid import UUID
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse
from journeys.collaboration_services import artifact_for_download, ensure_case_access
from requirements.domain_services import _require_manage
from requirements.models import JourneyRequirementAssessment, RequirementDefinition

TARGETS = {
    "journey_artifact": "journey_artifact",
    "requirement_definition": "requirement_definition",
    "journey_requirement_assessment": "journey_requirement_assessment",
}


def authorized_target(actor, kind, identifier):
    if kind == "journey_artifact":
        return artifact_for_download(actor=actor, artifact_id=identifier)
    if kind == "requirement_definition":
        obj = RequirementDefinition.objects.select_related("activity").filter(pk=identifier).first()
        if obj is not None:
            _require_manage(actor, obj.activity)
            return obj
    if kind == "journey_requirement_assessment":
        obj = JourneyRequirementAssessment.objects.select_related("journey__activity", "requirement").filter(pk=identifier).first()
        if obj is not None:
            ensure_case_access(actor, obj.journey, write=False)
            if obj.journey.beneficiary_id != actor.pk:
                _require_manage(actor, obj.journey.activity)
            return obj
    raise PermissionDenied("Référence inaccessible.")


def validate_references(actor, values, *, check_access=True):
    if not isinstance(values, (list, tuple)) or len(values) > 10:
        raise ValidationError({"references": "10 références maximum."})
    result, seen = [], set()
    for item in values:
        if not isinstance(item, dict) or set(item) != {"kind", "id"} or item["kind"] not in TARGETS:
            raise ValidationError({"references": "Référence invalide."})
        try:
            identifier = UUID(str(item["id"]))
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValidationError({"references": "Référence invalide."}) from exc
        marker = (item["kind"], str(identifier))
        if marker in seen:
            raise ValidationError({"references": "Référence dupliquée."})
        seen.add(marker)
        if check_access:
            authorized_target(actor, item["kind"], identifier)
        result.append({"kind": item["kind"], "id": str(identifier)})
    return result


def project_reference(actor, reference):
    kind = next(k for k in TARGETS if getattr(reference, f"{k}_id") is not None)
    obj = authorized_target(actor, kind, getattr(reference, f"{kind}_id"))
    label = obj.requirement.title if kind == "journey_requirement_assessment" else obj.title
    result = {"id": str(reference.pk), "kind": kind, "label": label, "available": True}
    if kind == "journey_artifact":
        result["download_url"] = reverse("journeys:artifact-download", kwargs={"artifact_id": obj.pk})
        result.update(version=obj.version, size=obj.size, mime_type=obj.mime_type, state_label=obj.get_status_display())
    if kind == "requirement_definition":
        result.update(version=obj.version, mode_label=obj.get_mode_display(), state_label=obj.get_status_display())
    if kind == "journey_requirement_assessment":
        result["state"] = obj.state
        result["state_label"] = obj.get_state_display()
    return result
