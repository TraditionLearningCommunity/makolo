from types import MappingProxyType

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import TemplateView

from authorization.constants import PermissionCode
from authorization.services import can
from organizations.models import Organization

from .contexts import PresentationContext
from .enums import PresentationPurpose, Provenance, VersionStatus, Visibility
from .library_models import PresentationTemplateModeration, SpacePresentationDefault
from .library_services import duplicate_template, publish_template_version, retire_template_version, set_space_default, submit_template_version, suspend_template_version
from .models import PresentationTemplate, PresentationTemplateVersion, PresentationThemeVersion
from .rendering import render_presentation


def _version_accessible(actor, version):
    template = version.template
    if template.visibility == Visibility.PUBLIC:
        return True
    if template.owner_profile_id == getattr(actor, "pk", None):
        return True
    return bool(template.owner_space_id and can(actor, PermissionCode.SPACE_VIEW, template.owner_space))


def _demo_context():
    freeze = lambda value: MappingProxyType(dict(value))
    return PresentationContext(
        activity=freeze({"display_title": "Activité Makolo", "description": "Aperçu du modèle avec des données de démonstration.", "kind": "activity"}),
        occurrence=freeze({"starts_at": "18/09/2026 · 18:00", "ends_at": "20:00", "place": "Lieu Makolo"}),
        organizer=freeze({"display_name": "Organisation Makolo", "public_logo": ""}),
        recipient=freeze({"display_name": "Participant"}),
        access=freeze({"display_type": "Accès", "display_status": "Valide", "beneficiary": "Participant"}),
        editorial=freeze({"eyebrow": "Invitation", "intro": "Bienvenue.", "invitation_message": "Nous avons le plaisir de vous inviter.", "instructions": "Présentez votre accès à l’entrée.", "dress_code": "", "contact_text": "", "signature": "", "hero_image": "", "footer_note": "Propulsé par Makolo"}),
        actions=freeze({"primary_url": "", "primary_label": ""}),
        render_assets=freeze({}),
    )


class PresentationLibraryView(LoginRequiredMixin, TemplateView):
    template_name = "presentations/library.html"
    login_url = "core:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        public = PresentationTemplate.objects.filter(visibility=Visibility.PUBLIC).prefetch_related("versions").order_by("name")
        context.update({
            "makolo_templates": public.filter(provenance=Provenance.MAKOLO),
            "community_templates": public.exclude(provenance=Provenance.MAKOLO),
            "my_templates": PresentationTemplate.objects.filter(owner_profile=self.request.user).prefetch_related("versions").order_by("name"),
            "submitted_templates": PresentationTemplateModeration.objects.select_related("version__template", "submitted_by").filter(version__status=VersionStatus.SUBMITTED).order_by("submitted_at") if self.request.user.is_staff else [],
        })
        return context


class SpacePresentationLibraryView(LoginRequiredMixin, TemplateView):
    template_name = "presentations/space_library.html"
    login_url = "core:login"

    def dispatch(self, request, *args, **kwargs):
        self.space = get_object_or_404(Organization, slug=kwargs["slug"])
        if not can(request.user, PermissionCode.SPACE_VIEW, self.space):
            raise PermissionDenied("Bibliothèque Espace inaccessible.")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        can_manage = can(self.request.user, PermissionCode.SPACE_MANAGE, self.space)
        templates = PresentationTemplate.objects.filter(owner_space=self.space).prefetch_related("versions").order_by("name")
        public_versions = PresentationTemplateVersion.objects.filter(status=VersionStatus.PUBLISHED, template__visibility=Visibility.PUBLIC).select_related("template").order_by("template__name", "-version_number")
        space_versions = PresentationTemplateVersion.objects.filter(status=VersionStatus.PUBLISHED, template__owner_space=self.space).select_related("template").order_by("template__name", "-version_number")
        public_themes = PresentationThemeVersion.objects.filter(status=VersionStatus.PUBLISHED, theme__visibility=Visibility.PUBLIC).select_related("theme").order_by("theme__name", "-version_number")
        space_themes = PresentationThemeVersion.objects.filter(status=VersionStatus.PUBLISHED, theme__owner_space=self.space).select_related("theme").order_by("theme__name", "-version_number")
        context.update({
            "space": self.space,
            "templates": templates,
            "can_manage_library": can_manage,
            "defaults": {item.purpose: item for item in SpacePresentationDefault.objects.filter(space=self.space).select_related("template_version__template", "theme_version__theme")},
            "purposes": PresentationPurpose.choices,
            "available_template_versions": list(public_versions) + list(space_versions),
            "available_theme_versions": list(public_themes) + list(space_themes),
        })
        return context


class SetSpaceDefaultView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, slug):
        space = get_object_or_404(Organization, slug=slug)
        purpose = request.POST.get("purpose")
        if purpose not in PresentationPurpose.values:
            return HttpResponseBadRequest("Usage invalide.")
        template_version = get_object_or_404(PresentationTemplateVersion.objects.select_related("template"), pk=request.POST.get("template_version"))
        theme_version = get_object_or_404(PresentationThemeVersion.objects.select_related("theme"), pk=request.POST.get("theme_version"))
        set_space_default(actor=request.user, space=space, purpose=purpose, template_version=template_version, theme_version=theme_version)
        messages.success(request, "Default de Présentation mis à jour.")
        return redirect("presentations:space-library", slug=space.slug)


class DuplicateTemplateView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, version_id):
        source = get_object_or_404(PresentationTemplateVersion.objects.select_related("template", "template__owner_space"), pk=version_id)
        if not _version_accessible(request.user, source):
            raise PermissionDenied("Modèle inaccessible.")
        owner_space = get_object_or_404(Organization, slug=request.POST["space_slug"]) if request.POST.get("space_slug") else None
        duplicate_template(actor=request.user, source_version=source, slug=(request.POST.get("slug") or f"{source.template.slug}-copie"), name=(request.POST.get("name") or f"{source.template.name} — copie"), owner_space=owner_space)
        messages.success(request, "Modèle dupliqué dans votre bibliothèque.")
        return redirect("presentations:space-library", slug=owner_space.slug) if owner_space else redirect("presentations:library")


class TemplateVersionPreviewView(LoginRequiredMixin, View):
    login_url = "core:login"

    def get(self, request, version_id):
        version = get_object_or_404(PresentationTemplateVersion.objects.select_related("template", "template__owner_space"), pk=version_id)
        if not _version_accessible(request.user, version):
            raise PermissionDenied("Aperçu inaccessible.")
        try:
            html = render_presentation(manifest=version.manifest, theme_tokens={"background": "#FAF7F5", "surface": "#FFFFFF", "text": "#0F172A", "muted": "#475569", "accent": "#5232DB", "font_family": "system", "radius": "md", "density": "normal", "border_style": "solid", "motion": "none"}, context=_demo_context(), surface="web")
        except ValidationError:
            return HttpResponseBadRequest("Ce modèle ne peut pas être prévisualisé tant que son manifest est invalide.")
        return HttpResponse(f'<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/static/presentations/mps.css"></head><body>{html}</body></html>', content_type="text/html; charset=utf-8")


class SubmitTemplateView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, version_id):
        version = get_object_or_404(PresentationTemplateVersion.objects.select_related("template", "template__owner_space"), pk=version_id)
        submit_template_version(actor=request.user, version=version)
        messages.success(request, "Modèle soumis à la revue Makolo.")
        return redirect("presentations:library")


class ModerateTemplateView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, version_id, action):
        version = get_object_or_404(PresentationTemplateVersion.objects.select_related("template", "template__owner_space"), pk=version_id)
        if action == "publish":
            publish_template_version(actor=request.user, version=version, note=request.POST.get("note", ""))
        elif action == "suspend":
            suspend_template_version(actor=request.user, version=version, note=request.POST.get("note", ""))
        elif action == "retire":
            retire_template_version(actor=request.user, version=version)
        else:
            raise PermissionDenied("Action de modération inconnue.")
        messages.success(request, "État du modèle mis à jour.")
        return redirect("presentations:library")
