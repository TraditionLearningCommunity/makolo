from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.core import signing
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.generic import TemplateView

from core.branding import render_makolo_qr_data_uri

from organizations.models import Organization
from organizations.permissions import user_can_access_organization_workspace, user_can_manage_organization, user_can_manage_organization_team

from .models import PassportSnapshot, PublicIdentifier, PublicSubjectKind
from .passport_pdf import passport_pdf_response
from .passport_documents import (
    issue_passport_snapshot,
    passport_verification_token,
    resolve_passport_verification_token,
    snapshot_payload_is_intact,
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
        if variant not in PASSPORT_VARIANTS:
            raise Http404("Variante du Passeport inconnue.")
        return variant

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
        params.pop("pdf", None)
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
            and (not self.has_custom_selection() or self.request.GET.get("edit") == "1")
            and not any(
                self.request.GET.get(mode) == "1"
                for mode in ("download", "document", "pdf")
            )
        )
        is_pdf = self.request.GET.get("pdf") == "1"
        is_export = self.request.GET.get("download") == "1"
        is_print_document = self.request.GET.get("document") == "1"
        is_document = is_export or is_print_document or is_pdf
        snapshot = None
        verification_url = ""
        qr_data_uri = ""
        if projection.has_content and is_document and not is_pdf:
            snapshot = issue_passport_snapshot(projection)
            token = passport_verification_token(snapshot)
            verification_url = self.request.build_absolute_uri(
                reverse("sharing:passport-verify", kwargs={"token": token})
            )
            qr_data_uri = render_makolo_qr_data_uri(verification_url, box_size=5)

        if is_document and not projection.has_content:
            raise Http404("Ce Passeport ne contient encore rien à exporter.")

        public_url = ""
        try:
            public_identifier = self.subject.public_identifier_record.identifier
            if self.subject_is_public():
                public_url = self.request.build_absolute_uri(
                    reverse("public-passport", kwargs={"identifier": public_identifier})
                )
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
                "can_edit_custom_selection": (
                    self.private_authorized and self.variant == PASSPORT_CUSTOM
                    and self.has_custom_selection() and not is_document
                    and not show_selection_catalog
                ),
                "edit_selection_url": self._document_url("edit"),
                "selected_topic_codes": set(self.request.GET.getlist("topic")),
                "selected_sections": set(self.request.GET.getlist("include")),
                "selected_activity_ids": set(self.request.GET.getlist("activity")),
                "selected_proof_ids": set(self.request.GET.getlist("proof")),
                "selected_credential_ids": set(self.request.GET.getlist("credential")),
                "download_url": self.get_download_url(),
                "print_url": self.get_print_url(),
                "pdf_url": self._document_url("pdf"),
                "can_export": projection.has_content,
                "is_export": is_export,
                "is_document": is_document,
                "auto_print": is_print_document,
                "public_identifier": public_identifier,
                "public_passport_url": public_url,
                "passport_is_audience_view": (
                    projection.subject_kind == "profile"
                    and self.variant == PASSPORT_PUBLIC
                    and self.request.GET.get("audience") == "mine"
                    and not is_document
                ),
                "passport_can_view_audience": (
                    projection.subject_kind == "profile"
                    and self.variant == PASSPORT_PUBLIC
                    and self.request.user.is_authenticated
                    and self.request.user.pk != self.subject.pk
                    and not is_document
                ),
                "passport_history_url": (
                    reverse("sharing:passport-me-history")
                    if self.private_authorized and projection.subject_kind == "profile"
                    else (
                        reverse("sharing:passport-space-history",
                                kwargs={"slug": self.subject.slug})
                        if self.private_authorized and projection.subject_kind == "space"
                        else ""
                    )
                ),
                "passport_snapshot": snapshot,
                "passport_verification_url": verification_url,
                "passport_qr_data_uri": qr_data_uri,
            }
        )
        # Display owner-only coordinates on both /passport/me/ and the canonical
        # /<identifier>/ route when the authenticated person is the subject.
        if (projection.subject_kind == "profile" and self.variant == PASSPORT_COMPLETE
                and self.private_authorized and not is_document
                and self.request.user.is_authenticated
                and self.request.user.pk == self.subject.pk):
            details = projection.identity.get("owner_details", {})
            labels = (
                ("Prénom", "first_name"), ("Nom", "last_name"),
                ("Identifiant Makolo", "username"), ("Entreprise", "company"),
                ("Organisation", "organization"), ("Ville", "city"),
                ("Pays", "country"), ("Langue", "language"),
                ("Téléphone", "phone"), ("Adresse", "address"),
                ("Date de naissance", "birth_date"), ("Genre", "gender"),
            )
            context["owner_details"] = [
                (label, details[key]) for label, key in labels if details.get(key)
            ]
        return context

    def render_to_response(self, context, **response_kwargs):
        if self.request.GET.get("pdf") == "1":
            return passport_pdf_response(self.request, context["projection"])
        response = super().render_to_response(context, **response_kwargs)
        # Private owner views and personalized representations must not be
        # cached or served to a subsequent viewer by shared intermediaries.
        response["Cache-Control"] = "private, no-store"
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
            # Collective visibility is not a permission to export a
            # non-public fact as a publicly verifiable document.
            viewer=(
                self.request.user if (
                    variant == PASSPORT_PUBLIC
                    and self.request.GET.get("audience") == "mine"
                    and not any(self.request.GET.get(mode) == "1"
                                for mode in ("download", "document", "pdf"))
                ) else None
            ),
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
            include_private_teams=(
                variant == PASSPORT_COMPLETE
                and user_can_manage_organization_team(self.request.user, self.subject)
            ),
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
        viewer = self.request.user
        if not viewer.is_authenticated:
            return False
        if self.identifier_record.subject_kind == PublicSubjectKind.PROFILE:
            return viewer.pk == self.subject.pk
        return user_can_access_organization_workspace(viewer, self.subject)

    def subject_is_public(self):
        if self.identifier_record.subject_kind == PublicSubjectKind.PROFILE:
            return profile_has_public_passport(self.subject)
        return space_has_public_passport(self.subject)

    def build_projection(self, variant):
        # Reuse the exact subject-bound selection and admission rules of the
        # explicit routes, never elevate permissions through an identifier.
        if self.identifier_record.subject_kind == PublicSubjectKind.PROFILE:
            return ProfilePassportView.build_projection(self, variant)
        return SpacePassportView.build_projection(self, variant)

    def get_selection_catalog(self):
        if self.identifier_record.subject_kind == PublicSubjectKind.PROFILE:
            return ProfilePassportView.get_selection_catalog(self)
        return SpacePassportView.get_selection_catalog(self)

    def get_topic_options(self):
        if self.identifier_record.subject_kind == PublicSubjectKind.PROFILE:
            return ProfilePassportView.get_topic_options(self)
        return SpacePassportView.get_topic_options(self)



def _snapshot_content_allowed(snapshot, viewer, *, currently_public):
    """Do not let a document token grant permissions or expose current data."""
    if not snapshot_payload_is_intact(snapshot):
        return False
    # Issuance/publication is not Sharing. A version may have been issued
    # privately even though the Profile is now public. Both times must allow
    # general access, and revocation prevents public document access.
    if (not snapshot.is_revoked and snapshot.variant == PASSPORT_PUBLIC
            and snapshot.public_at_issue and currently_public):
        return True
    if not viewer.is_authenticated:
        return False
    if snapshot.subject_kind == PublicSubjectKind.PROFILE:
        return snapshot.profile_id == viewer.pk
    if not snapshot.space_id or not user_can_access_organization_workspace(viewer, snapshot.space):
        return False
    # History is owner-readable, even after revocation. Internal Space teams
    # still require their separate authority at reading time.
    if (snapshot.payload.get("space_teams") and
            not user_can_manage_organization_team(viewer, snapshot.space)):
        return False
    return True


class PassportVerificationView(TemplateView):
    """A signed address resolves one dated Passport, never a live recomposition."""
    template_name = "sharing/passport_verify.html"

    def get_snapshot(self):
        try:
            return resolve_passport_verification_token(self.kwargs["token"])
        except (signing.BadSignature, KeyError, ValueError, ObjectDoesNotExist) as exc:
            raise Http404("Ce document Makolo ne peut pas être vérifié.") from exc

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        snapshot = self.get_snapshot()
        if snapshot.subject_kind == PublicSubjectKind.PROFILE:
            currently_public = bool(
                snapshot.profile and snapshot.profile.is_active
                and profile_has_public_passport(snapshot.profile)
            )
        else:
            currently_public = bool(snapshot.space and space_has_public_passport(snapshot.space))
        intact = snapshot_payload_is_intact(snapshot)
        allowed = _snapshot_content_allowed(
            snapshot, self.request.user, currently_public=currently_public,
        )
        context.update({
            "snapshot": snapshot,
            "snapshot_name": (
                snapshot.payload.get("identity", {}).get(
                    "name", snapshot.public_identifier,
                )
                if allowed else snapshot.public_identifier
            ),
            "currently_public": currently_public,
            "snapshot_intact": intact,
            "can_view_dated_passport": allowed,
            "dated_payload": snapshot.payload if allowed else {},
        })
        return context

    def render_to_response(self, context, **response_kwargs):
        response = super().render_to_response(context, **response_kwargs)
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        response["Referrer-Policy"] = "no-referrer"
        response["X-Robots-Tag"] = "noindex, nofollow"
        return response


class PassportHistoryBase(LoginRequiredMixin, TemplateView):
    """Paginated owner-authorized list of actually issued immutable snapshots."""
    template_name = "sharing/passport_history.html"

    def get_subject(self):
        raise NotImplementedError

    def can_view(self, viewer, subject):
        raise NotImplementedError

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        self.history_subject = self.get_subject()
        if not self.can_view(request.user, self.history_subject):
            raise PermissionDenied("Historique du Passeport non autorisé.")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        subject = self.history_subject
        if isinstance(self, MyPassportHistoryView):
            queryset = PassportSnapshot.objects.filter(profile=subject)
            title = subject.full_name or subject.username
            current_url = reverse("sharing:passport-me")
        else:
            queryset = PassportSnapshot.objects.filter(space=subject)
            title = subject.name
            current_url = reverse(
                "sharing:passport-space", kwargs={"slug": subject.slug},
            )
        page = Paginator(
            queryset.prefetch_related(
                "passport_share_subjects__envelope",
            ).order_by("-generated_at", "-pk"), 20,
        ).get_page(self.request.GET.get("page"))
        context.update({
            "history_subject_name": title,
            "current_passport_url": current_url,
            "history_page": page,
            "can_share_issued_passport": (
                isinstance(self, MyPassportHistoryView)
                or user_can_manage_organization(self.request.user, subject)
            ),
            "history_rows": [
                {
                    "snapshot": row,
                    "intact": snapshot_payload_is_intact(row),
                    "url": reverse(
                        "sharing:passport-verify",
                        kwargs={"token": passport_verification_token(row)},
                    ),
                    "share_url": reverse(
                        "sharing:passport-share-create",
                        kwargs={"snapshot_id": row.pk},
                    ),
                    "share_grants": [
                        {
                            "envelope": grant.envelope,
                            "revoke_url": reverse(
                                "sharing:passport-share-revoke",
                                kwargs={"share_id": grant.envelope_id},
                            ),
                        }
                        for grant in row.passport_share_subjects.all()
                        if grant.envelope.is_active_at()
                    ],
                }
                for row in page.object_list
            ],
        })
        return context

    def render_to_response(self, context, **response_kwargs):
        response = super().render_to_response(context, **response_kwargs)
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        response["Referrer-Policy"] = "no-referrer"
        response["X-Robots-Tag"] = "noindex, nofollow"
        return response


class MyPassportHistoryView(PassportHistoryBase):
    def get_subject(self):
        return self.request.user

    def can_view(self, viewer, subject):
        return viewer.is_authenticated and viewer.pk == subject.pk


class SpacePassportHistoryView(PassportHistoryBase):
    def get_subject(self):
        return get_object_or_404(Organization, slug=self.kwargs["slug"])

    def can_view(self, viewer, subject):
        return bool(
            viewer.is_authenticated
            and user_can_access_organization_workspace(viewer, subject)
        )
