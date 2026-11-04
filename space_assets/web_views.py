"""Compact institutional document UX, with current Space authority at every action."""
from django.contrib import messages
from django.contrib.auth import get_user_model
from authorization.constants import PermissionCode
from authorization.selectors import has_direct_space_permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import FileResponse, Http404
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.text import slugify
from django.views.decorators.http import require_POST
from journeys.models import Journey, TERMINAL_JOURNEY_STATUSES
from journeys.collaboration_services import ensure_case_access
from django.utils.decorators import method_decorator

from organizations.space_web_views import SpaceWebMixin

from .models import SpaceDocument, SpaceDocumentVersion, SpaceDocumentVisibility
from .services import (
    add_document_version, archive_document, can_manage_documents,
    can_read_document, create_document, update_document, version_for_download,
    visible_documents,
)


class SpaceDocumentsWebView(SpaceWebMixin):
    template_name = "space_assets/library.html"
    space_nav_key = "us"
    space_page_title = "Documents"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if not (
            can_manage_documents(self.request.user, self.space)
            or has_direct_space_permission(
                self.request.user, self.space, PermissionCode.SPACE_VIEW,
            )
        ):
            raise Http404
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
        from sharing.models import ShareDelivery, ShareSubjectType
        grants = (
            ShareDelivery.objects.select_related("recipient__user", "envelope")
            .filter(
                envelope__subject_type=ShareSubjectType.SPACE_DOCUMENT,
                envelope__space_document_subject__version__document=document,
            ).order_by("-delivered_at")[:20]
            if can_manage_documents(self.request.user, self.space) else []
        )
        eligible = []
        for journey in Journey.objects.select_related("activity").filter(
            activity__space=self.space,
        ).exclude(status__in=TERMINAL_JOURNEY_STATUSES).order_by("-updated_at", "id")[:120]:
            try:
                ensure_case_access(self.request.user, journey, write=True)
            except PermissionDenied:
                continue
            eligible.append(journey)
            if len(eligible) >= 20:
                break
        context.update({
            "eligible_journeys": eligible,
            "share_rows": grants,
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


class SpaceDocumentPreviewWebView(SpaceWebMixin):
    """Inline view only for validated, inert browser-viewable formats."""
    space_nav_key = "us"
    inline_types = {"application/pdf", "image/jpeg", "image/png"}

    def get(self, request, *args, **kwargs):
        try:
            version = version_for_download(
                actor=request.user, space=self.space,
                version_id=self.kwargs["version_id"],
            )
        except PermissionDenied as exc:
            raise Http404 from exc
        if version.mime_type not in self.inline_types:
            raise Http404
        response = FileResponse(
            version.file.open("rb"), as_attachment=False,
            filename=f"{slugify(version.document.title) or 'document'}-v{version.version}",
            content_type=version.mime_type,
        )
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        response["Content-Security-Policy"] = "sandbox"
        response["Referrer-Policy"] = "no-referrer"
        response["X-Frame-Options"] = "SAMEORIGIN"
        return response


class SpaceDocumentShareWebView(SpaceWebMixin):
    space_nav_key = "us"

    def post(self, request, *args, **kwargs):
        from sharing.space_document_sharing import share_space_document
        if not can_manage_documents(request.user, self.space):
            raise Http404
        doc = SpaceDocument.objects.filter(
            pk=self.kwargs["document_id"], space=self.space,
            archived_at__isnull=True,
        ).first()
        if doc is None:
            raise Http404
        version = doc.versions.order_by("-version").first()
        username = (request.POST.get("recipient") or "").strip().removeprefix("@")
        recipient = get_user_model().objects.filter(
            username__iexact=username,
            profile__isnull=False, is_active=True,
        ).select_related("profile").first()
        if version is None or recipient is None:
            messages.error(request, "Destinataire indisponible.")
            return redirect(_space_document_url(self.space, doc))
        try:
            share_space_document(
                actor=request.user, version=version, recipient=recipient.profile,
                days=int(request.POST.get("days", "7")),
            )
        except (PermissionDenied, ValidationError, ValueError, TypeError):
            messages.error(request, "Partage impossible.")
        else:
            messages.success(request, "Document partagé.")
        return redirect(_space_document_url(self.space, doc))


class SpaceDocumentShareRevokeWebView(SpaceWebMixin):
    space_nav_key = "us"

    def post(self, request, *args, **kwargs):
        from sharing.space_document_sharing import revoke_space_document_share
        from sharing.services import ShareUnavailable
        from sharing.models import ShareDelivery, ShareSubjectType
        if not can_manage_documents(request.user, self.space):
            raise Http404
        delivery = ShareDelivery.objects.filter(
            pk=self.kwargs["delivery_id"],
            envelope__subject_type=ShareSubjectType.SPACE_DOCUMENT,
            envelope__space_document_subject__version__document__space=self.space,
        ).select_related("envelope__space_document_subject__version").first()
        if delivery is None:
            raise Http404
        doc = delivery.envelope.space_document_subject.version.document
        try:
            revoke_space_document_share(
                actor=request.user, delivery_id=delivery.pk,
            )
        except (PermissionDenied, ShareUnavailable) as exc:
            raise Http404 from exc
        messages.success(request, "Partage révoqué.")
        return redirect(_space_document_url(self.space, doc))


class SpaceDocumentReuseWebView(SpaceWebMixin):
    space_nav_key = "us"

    def post(self, request, *args, **kwargs):
        from .services import use_document_in_journey
        doc = SpaceDocument.objects.filter(
            pk=self.kwargs["document_id"], space=self.space,
            archived_at__isnull=True,
        ).select_related("space").first()
        if doc is None or not can_read_document(request.user, doc):
            raise Http404
        version = doc.versions.order_by("-version").first()
        if version is None:
            raise Http404
        journey = Journey.objects.select_related("activity").filter(
            pk=request.POST.get("journey_id"), activity__space=self.space,
        ).first()
        if journey is None:
            raise Http404
        try:
            artifact = use_document_in_journey(
                actor=request.user, document_version=version, journey=journey,
            )
        except PermissionDenied as exc:
            raise Http404 from exc
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
            return redirect(_space_document_url(self.space, doc))
        messages.success(request, "Document ajouté à la démarche.")
        return redirect("core:participant-journey-detail", pk=journey.pk)


class SpaceDocumentUpdateWebView(SpaceWebMixin):
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
            update_document(
                actor=request.user, document=doc,
                title=request.POST.get("title", ""),
                visibility=request.POST.get("visibility", "restricted"),
            )
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
        else:
            messages.success(request, "Document actualisé.")
        return redirect(_space_document_url(self.space, doc))
