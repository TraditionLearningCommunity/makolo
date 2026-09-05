from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.views.generic import TemplateView

from organizations.models import Organization
from organizations.permissions import user_can_access_organization_workspace

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

    def get_download_url(self):
        params = self.request.GET.copy()
        params["download"] = "1"
        return f"{self.request.path}?{params.urlencode()}"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        projection = self.build_projection(self.variant)
        show_selection_catalog = (
            self.private_authorized
            and self.variant == PASSPORT_CUSTOM
            and not self.has_custom_selection()
            and self.request.GET.get("download") != "1"
        )
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
        return str(projection.subject.pk)


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
