from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404

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
