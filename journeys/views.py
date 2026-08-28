from django.contrib.auth.decorators import login_required
from django.http import FileResponse
from django.utils.text import slugify

from .collaboration_services import artifact_for_download


@login_required
def download_artifact(request, artifact_id):
    artifact = artifact_for_download(actor=request.user, artifact_id=artifact_id)
    response = FileResponse(
        artifact.file.open("rb"),
        as_attachment=True,
        filename=f"{slugify(artifact.title) or 'artifact'}-v{artifact.version}",
        content_type=artifact.mime_type,
    )
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"
    return response
