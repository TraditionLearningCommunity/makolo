from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404
from django.shortcuts import render
from django.utils.text import slugify

from sharing.document_services import export_decision_for_artifact


EXTENSION_BY_MIME = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/msword": ".doc",
    "text/plain": ".txt",
    "image/jpeg": ".jpg",
    "image/png": ".png",
}


@login_required(login_url="core:login")
def download_artifact(request, artifact_id):
    artifact, decision = export_decision_for_artifact(
        actor=request.user,
        artifact_id=artifact_id,
        channel="download",
    )
    if decision.requires_warning and request.GET.get("confirm") != "1":
        return render(request, "sharing/export_warning.html", {"artifact": artifact})
    extension = EXTENSION_BY_MIME.get(artifact.mime_type, "")
    filename = f"{slugify(artifact.title) or 'document'}-v{artifact.version}{extension}"
    try:
        handle = artifact.file.open("rb")
    except (FileNotFoundError, OSError) as exc:
        raise Http404("Document indisponible.") from exc
    response = FileResponse(
        handle,
        as_attachment=True,
        filename=filename,
        content_type=artifact.mime_type,
    )
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"
    return response
