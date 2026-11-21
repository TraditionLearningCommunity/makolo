from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404
from django.views.decorators.clickjacking import xframe_options_sameorigin

from .media_services import attachment_for_download


@login_required(login_url="core:login")
def serve_attachment(request, attachment_pk):
    try:
        attachment = attachment_for_download(actor=request.user, attachment_id=attachment_pk)
    except PermissionDenied as exc:
        raise Http404 from exc
    attachment.file.open("rb")
    response = FileResponse(attachment.file, as_attachment=True, filename=attachment.original_name, content_type=attachment.mime_type)
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"
    return response


INLINE_MEDIA_TYPES = {
    "image/jpeg", "image/png", "image/webp", "image/gif",
    "audio/webm", "audio/ogg", "audio/mp4", "audio/x-m4a",
    "audio/wav", "audio/mpeg",
    "video/mp4", "video/webm",
    # Explicitly safe browser viewers only. Never serve HTML or SVG inline.
    "application/pdf", "text/plain",
}


@login_required(login_url="core:login")
@xframe_options_sameorigin
def serve_inline_attachment(request, attachment_pk):
    """First-party inline rendition: same live ACL, no public storage URL."""
    try:
        attachment = attachment_for_download(
            actor=request.user, attachment_id=attachment_pk,
        )
    except PermissionDenied as exc:
        raise Http404 from exc
    if attachment.mime_type not in INLINE_MEDIA_TYPES:
        raise Http404("Aperçu non pris en charge.")
    attachment.file.open("rb")
    response = FileResponse(
        attachment.file, as_attachment=False,
        filename=attachment.original_name, content_type=attachment.mime_type,
    )
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"
    response["Content-Security-Policy"] = "default-src 'none'"
    return response
