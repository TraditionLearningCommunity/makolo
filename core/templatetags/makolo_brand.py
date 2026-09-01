from django import template

from access.models import CredentialStatus, CredentialType
from access.services import render_access_credential
from core.branding import render_makolo_qr_data_uri


register = template.Library()


@register.simple_tag
def makolo_access_qr(credential, *, branded=True, box_size=8):
    """Render an active canonical QR credential without exposing its token.

    The owning Access service still creates/signs the payload. The template only
    receives a data URI for presentation.
    """
    if not credential:
        return ""
    if credential.credential_type != CredentialType.QR or credential.status != CredentialStatus.ACTIVE:
        return ""
    token = render_access_credential(credential)
    return render_makolo_qr_data_uri(token, branded=branded, box_size=box_size)
