"""Export the selected, server-authorized Makolo Passport as an issued PDF.

Permissions, domain selections and presentation identity are determined by
Sharing/Passport before calling this function. The renderer consumes the exact
immutable snapshot; the QR proves issuance of that same snapshot.
"""
from datetime import timezone

from django.http import Http404, HttpResponse
from django.urls import reverse

from core.branding import render_makolo_qr_png
from .passport_documents import issue_passport_snapshot, passport_verification_token
from .passport_pdf_layout import render_passport_layout


def _permitted_portrait(projection):
    """Read only the current profile-owned media admitted by this variant."""
    if projection.subject_kind != "profile":
        return None
    if not projection.identity.get("avatar_url"):
        return None
    avatar = getattr(projection.subject, "avatar", None)
    if not avatar or not getattr(avatar, "name", None):
        return None
    try:
        with avatar.open("rb") as image_file:
            data = image_file.read(8 * 1024 * 1024 + 1)
        return data if len(data) <= 8 * 1024 * 1024 else None
    except (OSError, ValueError):
        return None


def passport_pdf_response(request, projection):
    """Issue one dated, printable, verifiable PDF of the selected variant."""
    if not projection.has_content:
        raise Http404("Ce Passeport ne contient aucun élément à exporter.")

    # One issuance. Never re-query or re-serialize data after this snapshot.
    snapshot = issue_passport_snapshot(projection)
    verification_url = request.build_absolute_uri(
        reverse(
            "sharing:passport-verify",
            kwargs={"token": passport_verification_token(snapshot)},
        )
    )
    issued = snapshot.generated_at.astimezone(timezone.utc)
    metadata = {
        "document_id": snapshot.document_id,
        "issued_at": issued.strftime("%d/%m/%Y · %H:%M UTC"),
        "variant": projection.variant_label,
        "identifier": snapshot.public_identifier,
    }
    content = render_passport_layout(
        snapshot.payload,
        metadata,
        verification_url,
        portrait_bytes=_permitted_portrait(projection),
        qr_png=render_makolo_qr_png(
            verification_url, branded=True, box_size=5,
        ),
    )
    response = HttpResponse(content, content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="passeport-makolo-{snapshot.document_id}.pdf"'
    )
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response
