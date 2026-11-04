"""Current-Space, permission-checked institutional document endpoints."""
from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils.text import slugify
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from journeys.models import Journey
from organizations.api.workspace_projection import workspace_spaces

from .models import SpaceDocument, SpaceDocumentVersion
from .services import (
    add_document_version, archive_document, can_manage_documents,
    can_read_document, create_document, update_document,
    use_document_in_journey, version_for_download, visible_documents,
)

PAGE_SIZE = 20


def _validation_error(exc):
    return ValidationError(
        getattr(exc, "message_dict", None)
        or {"document": getattr(exc, "messages", [str(exc)])}
    )


def _document_item(doc, *, detail=False):
    latest = doc.versions.order_by("-version").first()
    data = {
        "id": str(doc.pk), "title": doc.title, "kind": doc.kind,
        "visibility": doc.visibility,
        "updated_at": doc.updated_at.isoformat(),
        "latest_version": latest.version if latest else None,
        "version_id": str(latest.pk) if latest else None,
    }
    if detail:
        data["versions"] = [
            {
                "id": str(v.pk), "number": v.version,
                "mime_type": v.mime_type, "size": v.size,
                "issued_at": v.issued_at.isoformat() if v.issued_at else None,
                "expires_at": v.expires_at.isoformat() if v.expires_at else None,
            }
            for v in doc.versions.order_by("-version")[:30]
        ]
    return data


def _int_offset(request):
    try:
        raw = request.query_params.get("offset", "0")
        offset = int(raw)
    except (ValueError, TypeError) as exc:
        raise ValidationError({"offset": "Valeur invalide."}) from exc
    if offset < 0 or offset > 100000:
        raise ValidationError({"offset": "Valeur invalide."})
    return offset


class SpaceDocumentBase(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def space(self, request, slug):
        space = workspace_spaces(request.user).filter(slug=slug).first()
        if space is None:
            raise NotFound()
        return space

    def item(self, request, slug, document_id, *, manage=False):
        space = self.space(request, slug)
        doc = get_object_or_404(
            SpaceDocument.objects.select_related("space"),
            pk=document_id, space=space, archived_at__isnull=True,
        )
        if manage:
            if not can_manage_documents(request.user, space):
                raise NotFound()
        elif not can_read_document(request.user, doc):
            raise NotFound()
        return doc

    @staticmethod
    def respond(data, *, status=200):
        response = Response(data, status=status)
        response["Cache-Control"] = "private, no-store"
        return response


class SpaceDocumentCollectionAPIView(SpaceDocumentBase):
    def get(self, request, slug):
        space = self.space(request, slug)
        queryset = visible_documents(actor=request.user, space=space)
        if not can_manage_documents(request.user, space) and not queryset.exists():
            # An authorized empty library is different from an unauthorized one.
            from authorization.constants import PermissionCode
            from authorization.selectors import has_direct_space_permission
            if not has_direct_space_permission(
                request.user, space, PermissionCode.SPACE_VIEW
            ):
                raise NotFound()
        query = (request.query_params.get("q") or "").strip()[:120]
        if query:
            queryset = queryset.filter(title__icontains=query)
        offset = _int_offset(request)
        queryset = queryset.order_by("-updated_at", "id")
        rows = list(queryset[offset:offset + PAGE_SIZE + 1])
        return self.respond({
            "space_id": str(space.pk),
            "items": [_document_item(item) for item in rows[:PAGE_SIZE]],
            "has_more": len(rows) > PAGE_SIZE,
            "next_offset": offset + min(PAGE_SIZE, len(rows)),
            "can_manage": can_manage_documents(request.user, space),
        })

    def post(self, request, slug):
        space = self.space(request, slug)
        if not can_manage_documents(request.user, space):
            raise NotFound()
        try:
            document, version = create_document(
                actor=request.user, space=space,
                title=request.data.get("title", ""),
                kind=request.data.get("kind", "other"),
                visibility=request.data.get("visibility", "restricted"),
                uploaded_file=request.FILES.get("file"),
                issued_at=request.data.get("issued_at") or None,
                expires_at=request.data.get("expires_at") or None,
            )
        except DjangoValidationError as exc:
            raise _validation_error(exc) from exc
        return self.respond({
            "document": _document_item(document, detail=True),
            "version_id": str(version.pk),
        }, status=201)


class SpaceDocumentDetailAPIView(SpaceDocumentBase):
    def get(self, request, slug, document_id):
        doc = self.item(request, slug, document_id)
        return self.respond({
            "document": _document_item(doc, detail=True),
            "can_manage": can_manage_documents(request.user, doc.space),
        })

    def patch(self, request, slug, document_id):
        doc = self.item(request, slug, document_id, manage=True)
        try:
            updated = update_document(
                actor=request.user, document=doc,
                title=request.data.get("title"),
                visibility=request.data.get("visibility"),
            )
        except DjangoValidationError as exc:
            raise _validation_error(exc) from exc
        return self.respond({"document": _document_item(updated, detail=True)})

    def delete(self, request, slug, document_id):
        doc = self.item(request, slug, document_id, manage=True)
        archive_document(actor=request.user, document=doc)
        return self.respond({"archived": True})


class SpaceDocumentVersionCreateAPIView(SpaceDocumentBase):
    def post(self, request, slug, document_id):
        doc = self.item(request, slug, document_id, manage=True)
        try:
            version = add_document_version(
                actor=request.user, document=doc,
                uploaded_file=request.FILES.get("file"),
                issued_at=request.data.get("issued_at") or None,
                expires_at=request.data.get("expires_at") or None,
            )
        except DjangoValidationError as exc:
            raise _validation_error(exc) from exc
        return self.respond({"version_id": str(version.pk), "number": version.version}, status=201)


class SpaceDocumentDownloadAPIView(SpaceDocumentBase):
    def get(self, request, slug, version_id):
        space = self.space(request, slug)
        try:
            version = version_for_download(
                actor=request.user, space=space, version_id=version_id,
            )
        except DjangoPermissionDenied as exc:
            raise NotFound() from exc
        response = FileResponse(
            version.file.open("rb"),
            as_attachment=True,
            filename=f"{slugify(version.document.title) or 'document'}-v{version.version}",
            content_type=version.mime_type,
        )
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        response["Referrer-Policy"] = "no-referrer"
        return response


class SpaceDocumentReuseAPIView(SpaceDocumentBase):
    def post(self, request, slug, version_id):
        space = self.space(request, slug)
        try:
            version = version_for_download(
                actor=request.user, space=space, version_id=version_id,
            )
        except DjangoPermissionDenied as exc:
            raise NotFound() from exc
        journey = (
            Journey.objects.select_related("activity")
            .filter(pk=request.data.get("journey_id"), activity__space=space).first()
        )
        if journey is None:
            raise NotFound()
        try:
            artifact = use_document_in_journey(
                actor=request.user, document_version=version, journey=journey,
            )
        except DjangoPermissionDenied as exc:
            raise NotFound() from exc
        except DjangoValidationError as exc:
            raise _validation_error(exc) from exc
        return self.respond({
            "journey_artifact_id": str(artifact.pk),
            "status": "draft", "requirement_satisfied": False,
        }, status=201)
