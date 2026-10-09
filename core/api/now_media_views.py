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

# Uploaded content is not trusted. Never render active formats inline from the
# authenticated Makolo origin. Only explicitly supported inert viewers may
# receive inline content, with a restrictive CSP.
INLINE_MIME_TYPES = frozenset({
    "application/pdf",
    "image/jpeg", "image/png", "image/webp", "image/gif",
    "video/mp4", "video/webm", "audio/mpeg", "audio/mp4",
    "audio/ogg", "audio/wav",
})



def _docx_readable_text(file):
    """Bounded, non-executable text representation of a private DOCX."""
    try:
        with zipfile.ZipFile(file) as document:
            info = document.getinfo("word/document.xml")
            if info.file_size > MAX_DOCUMENT_TEXT:
                raise Http404
            with document.open(info) as stream:
                xml_bytes = stream.read(MAX_DOCUMENT_TEXT + 1)
            if len(xml_bytes) > MAX_DOCUMENT_TEXT:
                raise Http404
            # A document is user data: reject active XML constructs rather
            # than relying on parser-specific entity expansion limits.
            if b"<!DOCTYPE" in xml_bytes.upper() or b"<!ENTITY" in xml_bytes.upper():
                raise Http404
            root = ElementTree.fromstring(xml_bytes)
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
            response["Content-Security-Policy"] = "default-src 'none'; sandbox"
            response["Cross-Origin-Resource-Policy"] = "same-origin"
            return response

        mime = (artifact.mime_type or "").lower().strip()
        allowed_inline = mime in INLINE_MIME_TYPES
        response = FileResponse(
            artifact.file.open("rb"),
            content_type=mime if allowed_inline else "application/octet-stream",
            as_attachment=not allowed_inline,
            filename="document" if not allowed_inline else None,
        )
        if allowed_inline:
            response["Content-Disposition"] = "inline"
        response["Content-Security-Policy"] = "default-src 'none'; sandbox"
        response["Cross-Origin-Resource-Policy"] = "same-origin"
        response["X-Content-Type-Options"] = "nosniff"
        response["Cache-Control"] = "private, no-store"
        return response
