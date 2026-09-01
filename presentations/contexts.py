from dataclasses import dataclass, field
from types import MappingProxyType

from access.models import CredentialStatus, CredentialType
from access.services import render_access_credential
from core.branding import render_makolo_qr_data_uri


@dataclass(frozen=True)
class PresentationContext:
    activity: object
    occurrence: object | None
    organizer: object
    recipient: object
    access: object
    editorial: object
    actions: object
    render_assets: object = field(repr=False)

    def binding_value(self, binding):
        section, key = binding.split(".", 1)
        mapping = getattr(self, section, None)
        return "" if mapping is None else mapping.get(key, "")


def _freeze(data):
    return MappingProxyType(dict(data))


def build_activity_context(*, activity, occurrence=None, editorial=None, primary_url="", primary_label=""):
    if occurrence is not None and occurrence.activity_id != activity.pk:
        raise ValueError("Occurrence étrangère à l'Activity.")
    place = ""
    if occurrence is not None:
        link = occurrence.place_links.select_related("place").order_by("position", "role").first()
        if link:
            place = link.place.name
    return PresentationContext(
        activity=_freeze({"display_title": activity.title, "description": activity.description or activity.short_description, "kind": "activity"}),
        occurrence=_freeze({"starts_at": occurrence.start_at if occurrence else None, "ends_at": occurrence.end_at if occurrence else None, "place": place}),
        organizer=_freeze({"display_name": activity.operator_display_name, "public_logo": ""}),
        recipient=_freeze({"display_name": ""}),
        access=_freeze({"display_type": "", "display_status": "", "beneficiary": ""}),
        editorial=_freeze(editorial or {}),
        actions=_freeze({"primary_url": primary_url, "primary_label": primary_label}),
        render_assets=_freeze({}),
    )


def build_access_context(*, access, credential=None, editorial=None, primary_url="", primary_label="", display_type="Accès"):
    credential = credential or access.credentials.filter(credential_type=CredentialType.QR, status=CredentialStatus.ACTIVE).order_by("-version").first()
    qr_data_uri = ""
    if credential is not None:
        signed_payload = render_access_credential(credential)
        qr_data_uri = render_makolo_qr_data_uri(signed_payload)
    base = build_activity_context(activity=access.activity, occurrence=access.occurrence, editorial=editorial, primary_url=primary_url, primary_label=primary_label)
    return PresentationContext(
        activity=base.activity,
        occurrence=base.occurrence,
        organizer=base.organizer,
        recipient=_freeze({"display_name": access.beneficiary_display_name}),
        access=_freeze({"display_type": display_type, "display_status": access.get_status_display(), "beneficiary": access.beneficiary_display_name}),
        editorial=base.editorial,
        actions=base.actions,
        render_assets=_freeze({"canonical_qr_data_uri": qr_data_uri}),
    )
