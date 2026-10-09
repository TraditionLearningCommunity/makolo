"""Bearer-authenticated streaming of existing Journey artifacts used by Now.

The Journey owns the file and authorization. Now only references it.
"""
import zipfile
from xml.etree import ElementTree

from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404, HttpResponse
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from journeys.collaboration_services import artifact_for_download

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
MAX_DOCUMENT_TEXT = 512 * 1024


def _docx_readable_text(file):
    """Bounded, non-executable text representation of a private DOCX."""
    try:
        with zipfile.ZipFile(file) as document:
            info = document.getinfo("word/document.xml")
            if info.file_size > MAX_DOCUMENT_TEXT:
                raise Http404
            with document.open(info) as stream:
                root = ElementTree.fromstring(stream.read(MAX_DOCUMENT_TEXT + 1))
        namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        paragraphs = []
        for paragraph in root.findall(".//w:p", namespace):
            text = "".join(node.text or "" for node in paragraph.findall(".//w:t", namespace))
            if text.strip():
                paragraphs.append(text)
        return "\n".join(paragraphs)
    except (zipfile.BadZipFile, KeyError, ElementTree.ParseError, ValueError) as exc:
        raise Http404 from exc



class PersonalNowJourneyArtifactMediaAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, artifact_id):
        try:
            artifact = artifact_for_download(
                actor=request.user, artifact_id=artifact_id,
            )
        except PermissionDenied as exc:
            raise Http404 from exc
        if not artifact.file:
            raise Http404

        if request.query_params.get("view") == "text":
            mime = artifact.mime_type or ""
            if mime == DOCX_MIME:
                with artifact.file.open("rb") as source:
                    readable = _docx_readable_text(source)
            elif mime == "text/plain":
                with artifact.file.open("rb") as source:
                    readable = source.read(MAX_DOCUMENT_TEXT + 1).decode(
                        "utf-8", errors="replace"
                    )
                if len(readable) > MAX_DOCUMENT_TEXT:
                    raise Http404
            else:
                raise Http404
            response = HttpResponse(readable, content_type="text/plain; charset=utf-8")
            response["X-Content-Type-Options"] = "nosniff"
            response["Cache-Control"] = "private, no-store"
            return response

        response = FileResponse(
            artifact.file.open("rb"),
            content_type=artifact.mime_type or "application/octet-stream",
            as_attachment=False,
        )
        response["Content-Disposition"] = "inline"
        response["X-Content-Type-Options"] = "nosniff"
        response["Cache-Control"] = "private, no-store"
        return response
