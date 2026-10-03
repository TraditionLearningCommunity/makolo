from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core import signing
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.generic import TemplateView

from core.branding import render_makolo_qr_data_uri

from organizations.models import Organization
from organizations.permissions import user_can_access_organization_workspace

from .models import PublicIdentifier, PublicSubjectKind
from .passport_documents import (
    issue_passport_snapshot,
    passport_verification_token,
    resolve_passport_verification_token,
)

from .passport import (
    PASSPORT_COMPLETE,
    PASSPORT_CUSTOM,
    PASSPORT_PUBLIC,
    PASSPORT_VARIANTS,
    PASSPORT_VARIANT_LABELS,
    build_profile_passport,
    build_space_passport,
    profile_has_public_passport,
    profile_passport_topic_options,
    space_has_public_passport,
    space_passport_topic_options,
)


User = get_user_model()


class PassportViewMixin(TemplateView):
    template_name = "sharing/passport.html"
    default_variant = PASSPORT_PUBLIC

    def get_variant(self):
        variant = self.request.GET.get("variant", self.default_variant)
        return variant if variant in PASSPORT_VARIANTS else self.default_variant

    def is_private_authorized(self):
        raise NotImplementedError

    def get_subject(self):
        raise NotImplementedError

    def subject_is_public(self):
        raise NotImplementedError

    def build_projection(self, variant):
        raise NotImplementedError

    def get_selection_catalog(self):
        return None

    def get_topic_options(self):
        return ()

    def has_custom_selection(self):
        return any(
            self.request.GET.getlist(name)
            for name in ("activity", "proof", "credential", "include")
        )

    def dispatch(self, request, *args, **kwargs):
        self.subject = self.get_subject()
        self.private_authorized = self.is_private_authorized()
        if not self.subject_is_public() and not self.private_authorized:
            raise Http404("Ce Passeport Makolo n’est pas disponible publiquement.")
        variant = self.get_variant()
        if variant != PASSPORT_PUBLIC and not self.private_authorized:
            raise PermissionDenied("Cette variante du Passeport est réservée au sujet autorisé.")
        self.variant = variant
        return super().dispatch(request, *args, **kwargs)

    def _document_url(self, mode):
        params = self.request.GET.copy()
        params.pop("download", None)
        params.pop("document", None)
        params[mode] = "1"
        return f"{self.request.path}?{params.urlencode()}"

    def get_download_url(self):
        return self._document_url("download")

    def get_print_url(self):
        return self._document_url("document")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        projection = self.build_projection(self.variant)
        show_selection_catalog = (
            self.private_authorized
            and self.variant == PASSPORT_CUSTOM
            and not self.has_custom_selection()
            and self.request.GET.get("download") != "1"
        )
        is_export = self.request.GET.get("download") == "1"
        is_print_document = self.request.GET.get("document") == "1"
        is_document = is_export or is_print_document
        snapshot = None
        verification_url = ""
        qr_data_uri = ""
        if projection.has_content and is_document:
            snapshot = issue_passport_snapshot(projection)
            token = passport_verification_token(snapshot)
            verification_url = self.request.build_absolute_uri(
                reverse("sharing:passport-verify", kwargs={"token": token})
            )
            qr_data_uri = render_makolo_qr_data_uri(verification_url, box_size=5)

        if is_document and not projection.has_content:
            raise Http404("Ce Passeport ne contient encore rien à exporter.")

        try:
            public_identifier = self.subject.public_identifier_record.identifier
        except (AttributeError, ObjectDoesNotExist):
            public_identifier = getattr(self.subject, "username", None) or getattr(self.subject, "slug", "")

        context.update(
            {
                "projection": projection,
                "variant_labels": PASSPORT_VARIANT_LABELS,
                "can_use_private_variants": self.private_authorized,
                "subject_is_public": self.subject_is_public(),
                "topic_options": self.get_topic_options() if self.private_authorized else (),
                "selection_catalog": self.get_selection_catalog() if show_selection_catalog else None,
                "selected_topic_codes": set(self.request.GET.getlist("topic")),
                "download_url": self.get_download_url(),
                "print_url": self.get_print_url(),
                "can_export": projection.has_content,
                "is_export": is_export,
                "is_document": is_document,
                "auto_print": is_print_document,
                "public_identifier": public_identifier,
                "passport_snapshot": snapshot,
                "passport_verification_url": verification_url,
                "passport_qr_data_uri": qr_data_uri,
            }
        )
        return context

    def render_to_response(self, context, **response_kwargs):
        response = super().render_to_response(context, **response_kwargs)
        if self.request.GET.get("download") == "1":
            slug = self.projection_filename_slug(context["projection"])
            response["Content-Disposition"] = f'attachment; filename="passeport-makolo-{slug}.html"'
            response["Content-Type"] = "text/html; charset=utf-8"
        return response

    def projection_filename_slug(self, projection):
        if projection.subject_kind == "space":
            return projection.subject.slug
        return projection.subject.username


class ProfilePassportView(PassportViewMixin):
    def get_subject(self):
        return get_object_or_404(User.objects.filter(is_active=True), pk=self.kwargs["profile_id"])

    def is_private_authorized(self):
        return bool(self.request.user.is_authenticated and self.request.user.pk == self.subject.pk)

    def subject_is_public(self):
        return profile_has_public_passport(self.subject)

    def build_projection(self, variant):
        return build_profile_passport(
            self.subject,
            variant=variant,
            topic_codes=self.request.GET.getlist("topic"),
            selected_activity_ids=self.request.GET.getlist("activity") if variant == PASSPORT_CUSTOM else None,
            selected_proof_ids=self.request.GET.getlist("proof") if variant == PASSPORT_CUSTOM else None,
            selected_credential_ids=self.request.GET.getlist("credential") if variant == PASSPORT_CUSTOM else None,
            selected_sections=self.request.GET.getlist("include") if variant == PASSPORT_CUSTOM else None,
        )

    def get_selection_catalog(self):
        return build_profile_passport(self.subject, variant=PASSPORT_COMPLETE)

    def get_topic_options(self):
        return profile_passport_topic_options(self.subject)


class MyPassportView(LoginRequiredMixin, ProfilePassportView):
    default_variant = PASSPORT_COMPLETE

    def get_subject(self):
        return self.request.user


class SpacePassportView(PassportViewMixin):
    def get_subject(self):
        return get_object_or_404(Organization, slug=self.kwargs["slug"])

    def is_private_authorized(self):
        return bool(
            self.request.user.is_authenticated
            and user_can_access_organization_workspace(self.request.user, self.subject)
        )

    def subject_is_public(self):
        return space_has_public_passport(self.subject)

    def build_projection(self, variant):
        return build_space_passport(
            self.subject,
            variant=variant,
            topic_codes=self.request.GET.getlist("topic"),
            selected_activity_ids=self.request.GET.getlist("activity") if variant == PASSPORT_CUSTOM else None,
            selected_credential_ids=self.request.GET.getlist("credential") if variant == PASSPORT_CUSTOM else None,
            selected_sections=self.request.GET.getlist("include") if variant == PASSPORT_CUSTOM else None,
        )

    def get_selection_catalog(self):
        return build_space_passport(self.subject, variant=PASSPORT_COMPLETE)

    def get_topic_options(self):
        return space_passport_topic_options(self.subject)


class PublicPassportIdentifierView(PassportViewMixin):
    """Canonical public Passport at /<identifier>/ for Profile or Space."""

    default_variant = PASSPORT_PUBLIC

    def get_subject(self):
        try:
            self.identifier_record = PublicIdentifier.objects.select_related("profile", "space").get(
                identifier__iexact=self.kwargs["identifier"]
            )
        except PublicIdentifier.DoesNotExist as exc:
            raise Http404("Ce Passeport Makolo n’est pas disponible.") from exc
        subject = self.identifier_record.subject
        if self.identifier_record.subject_kind == PublicSubjectKind.PROFILE and not subject.is_active:
            raise Http404("Ce Passeport Makolo n’est pas disponible.")
        return subject

    def is_private_authorized(self):
        return False

    def subject_is_public(self):
        if self.identifier_record.subject_kind == PublicSubjectKind.PROFILE:
            return profile_has_public_passport(self.subject)
        return space_has_public_passport(self.subject)

    def build_projection(self, variant):
        if self.identifier_record.subject_kind == PublicSubjectKind.PROFILE:
            return build_profile_passport(self.subject, variant=PASSPORT_PUBLIC)
        return build_space_passport(self.subject, variant=PASSPORT_PUBLIC)


class PassportVerificationView(TemplateView):
    template_name = "sharing/passport_verify.html"

    def get_snapshot(self):
        try:
            return resolve_passport_verification_token(self.kwargs["token"])
        except (signing.BadSignature, KeyError, ObjectDoesNotExist) as exc:
            raise Http404("Ce document Makolo ne peut pas être vérifié.") from exc

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        snapshot = self.get_snapshot()
        if snapshot.subject_kind == PublicSubjectKind.PROFILE:
            currently_public = bool(snapshot.profile and profile_has_public_passport(snapshot.profile))
        else:
            currently_public = bool(snapshot.space and space_has_public_passport(snapshot.space))
        context.update(
            {
                "snapshot": snapshot,
                "snapshot_name": snapshot.payload.get("identity", {}).get("name", snapshot.public_identifier),
                "currently_public": currently_public,
            }
        )
        return context
