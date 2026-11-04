"""Compact institutional document UX, with current Space authority at every action."""
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import FileResponse, Http404
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.text import slugify
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator

from organizations.space_web_views import SpaceWebMixin

from .models import SpaceDocument, SpaceDocumentVersion, SpaceDocumentVisibility
from .services import (
    add_document_version, archive_document, can_manage_documents,
    can_read_document, create_document, version_for_download,
    visible_documents,
)


class SpaceDocumentsWebView(SpaceWebMixin):
    template_name = "space_assets/library.html"
    space_nav_key = "us"
    space_page_title = "Documents"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        search = (self.request.GET.get("q") or "").strip()[:120]
        documents = visible_documents(
            actor=self.request.user, space=self.space,
        ).order_by("-updated_at", "id")
        if search:
            documents = documents.filter(title__icontains=search)
        from django.core.paginator import Paginator
        page = Paginator(documents, 18).get_page(self.request.GET.get("page"))
        context.update({
            "document_rows": [
                {"document": doc, "latest": doc.versions.order_by("-version").first()}
                for doc in page.object_list
            ],
            "document_page": page,
            "document_query": search,
            "can_manage_documents": can_manage_documents(
                self.request.user, self.space,
            ),
            "document_visibility_choices": SpaceDocumentVisibility.choices,
        })
        return context


class SpaceDocumentDetailWebView(SpaceWebMixin):
    template_name = "space_assets/detail.html"
    space_nav_key = "us"
    space_page_title = "Document"

    def dispatch(self, request, *args, **kwargs):
        result = super().dispatch(request, *args, **kwargs)
        # dispatch may return an HTTP redirect or denial rather than a view.
        return result

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        document = (
            SpaceDocument.objects.select_related("space")
            .filter(pk=self.kwargs["document_id"], space=self.space)
            .first()
        )
        if document is None or (
            document.archived_at and not can_manage_documents(
                self.request.user, self.space,
            )
        ) or not can_read_document(self.request.user, document):
            raise Http404
        context.update({
            "document": document,
            "document_versions": document.versions.order_by("-version")[:30],
            "can_manage_documents": can_manage_documents(
                self.request.user, self.space,
            ) and not document.archived_at,
        })
        return context


def _space_document_url(space, doc):
    return reverse(
        "organizations:space-document-detail",
        kwargs={"slug": space.slug, "document_id": doc.pk},
    )


class SpaceDocumentUploadWebView(SpaceWebMixin):
    space_nav_key = "us"

    def post(self, request, *args, **kwargs):
        if not can_manage_documents(request.user, self.space):
            raise Http404
        try:
            doc, _ = create_document(
                actor=request.user, space=self.space,
                title=request.POST.get("title", ""),
                kind=request.POST.get("kind", "other"),
                visibility=request.POST.get("visibility", "restricted"),
                uploaded_file=request.FILES.get("file"),
            )
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
            return redirect(
                "organizations:space-documents", slug=self.space.slug,
            )
        messages.success(request, "Document ajouté.")
        return redirect(_space_document_url(self.space, doc))


class SpaceDocumentVersionWebView(SpaceWebMixin):
    space_nav_key = "us"

    def post(self, request, *args, **kwargs):
        if not can_manage_documents(request.user, self.space):
            raise Http404
        doc = SpaceDocument.objects.filter(
            pk=self.kwargs["document_id"], space=self.space,
            archived_at__isnull=True,
        ).first()
        if doc is None:
            raise Http404
        try:
            add_document_version(
                actor=request.user, document=doc,
                uploaded_file=request.FILES.get("file"),
            )
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
        else:
            messages.success(request, "Nouvelle version ajoutée.")
        return redirect(_space_document_url(self.space, doc))


class SpaceDocumentArchiveWebView(SpaceWebMixin):
    space_nav_key = "us"

    def post(self, request, *args, **kwargs):
        if not can_manage_documents(request.user, self.space):
            raise Http404
        doc = SpaceDocument.objects.filter(
            pk=self.kwargs["document_id"], space=self.space,
            archived_at__isnull=True,
        ).first()
        if doc is None:
            raise Http404
        archive_document(actor=request.user, document=doc)
        messages.success(request, "Document archivé.")
        return redirect("organizations:space-documents", slug=self.space.slug)


class SpaceDocumentDownloadWebView(SpaceWebMixin):
    space_nav_key = "us"

    def get(self, request, *args, **kwargs):
        try:
            version = version_for_download(
                actor=request.user, space=self.space,
                version_id=self.kwargs["version_id"],
            )
        except PermissionDenied as exc:
            raise Http404 from exc
        response = FileResponse(
            version.file.open("rb"), as_attachment=True,
            filename=f"{slugify(version.document.title) or 'document'}-v{version.version}",
            content_type=version.mime_type,
        )
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        response["Referrer-Policy"] = "no-referrer"
        return response
