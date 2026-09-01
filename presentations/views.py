from html import escape

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import TemplateView

from activities.models import Activity, ActivityVisibility
from authorization.constants import PermissionCode
from authorization.services import can
from core.participant_presentation import vocabulary_for
from core.participant_selectors import participant_accesses_visible_to_buyer

from .asset_services import create_presentation_asset
from .catalog import THEME_DEFINITIONS, catalog_entries, ensure_builtin_catalog
from .contexts import build_access_context, build_activity_context
from .editorial import PURPOSE_FIELDS
from .enums import PresentationPurpose, VersionStatus
from .rendering import render_presentation
from .resolver import ResolvedPresentation, resolve_presentation
from .services import configure_activity_presentation, publish_activity_presentation

PREVIEW_MODES = {"phone": "web", "desktop": "web", "print": "print"}
SAFE_PINNED_VERSION_STATUSES = {VersionStatus.PUBLISHED, VersionStatus.RETIRED}


def _occurrence(activity, raw_id=None):
    qs = activity.occurrences.prefetch_related("place_links__place").order_by("start_at", "id")
    return qs.filter(pk=raw_id).first() if raw_id else qs.first()


def _editorial_from_post(request, purpose, *, activity):
    allowed = PURPOSE_FIELDS.get(purpose, {})
    data = {
        key: request.POST.get(key, "").strip()
        for key in allowed
        if key != "hero_image" and request.POST.get(key, "").strip()
    }
    upload = request.FILES.get("hero_image")
    if upload and "hero_image" in allowed:
        asset = create_presentation_asset(actor=request.user, uploaded_file=upload, activity=activity, owner_space=activity.space)
        data["hero_image"] = asset.file.url
    return data


def _preview_resolution(activity, purpose):
    binding = activity.presentations.filter(occurrence__isnull=True, purpose=purpose).select_related("template_version", "theme_version").first()
    if binding and binding.template_version.status in SAFE_PINNED_VERSION_STATUSES and binding.theme_version.status in SAFE_PINNED_VERSION_STATUSES:
        return ResolvedPresentation(binding.template_version.manifest, binding.theme_version.tokens, binding, "draft-preview" if binding.state == "draft" else "")
    return resolve_presentation(activity=activity, purpose=purpose)


class ActivityPresentationAuthorityMixin(LoginRequiredMixin):
    login_url = "core:login"

    def dispatch(self, request, *args, **kwargs):
        self.activity = get_object_or_404(Activity.objects.select_related("space", "owner_profile"), pk=kwargs["activity_id"])
        if not can(request.user, PermissionCode.ACTIVITY_MANAGE, activity=self.activity):
            raise PermissionDenied("Vous n’avez pas l’autorité pour gérer la Présentation de cette Activity.")
        return super().dispatch(request, *args, **kwargs)


class ActivityPresentationStudioView(ActivityPresentationAuthorityMixin, TemplateView):
    template_name = "presentations/studio.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        ensure_builtin_catalog(actor=self.request.user)
        purpose = self.request.GET.get("purpose") or PresentationPurpose.PUBLIC_PAGE
        if purpose not in PresentationPurpose.values:
            purpose = PresentationPurpose.PUBLIC_PAGE
        current = self.activity.presentations.filter(occurrence__isnull=True, purpose=purpose).select_related("template_version__template", "theme_version__theme").first()
        editorial_fields = [{"name": field, "value": (current.editorial_data.get(field, "") if current else ""), "asset": field == "hero_image"} for field in PURPOSE_FIELDS.get(purpose, {})]
        context.update({"activity": self.activity, "purpose": purpose, "purposes": PresentationPurpose.choices, "catalog": catalog_entries(), "themes": [(slug, name) for slug, (name, _) in THEME_DEFINITIONS.items()], "current": current, "editorial_fields": editorial_fields, "public_url": reverse("presentations:public-activity", kwargs={"activity_id": self.activity.pk})})
        return context

    def post(self, request, *args, **kwargs):
        templates, themes = ensure_builtin_catalog(actor=request.user)
        purpose = request.POST.get("purpose") or PresentationPurpose.PUBLIC_PAGE
        template_slug = request.POST.get("template") or "makolo-essential"
        theme_slug = request.POST.get("theme") or "makolo-violet"
        if purpose not in PresentationPurpose.values or template_slug not in templates or theme_slug not in themes:
            raise ValidationError("Configuration de Présentation invalide.")
        presentation = configure_activity_presentation(actor=request.user, activity=self.activity, purpose=purpose, template_version=templates[template_slug], theme_version=themes[theme_slug], editorial_data=_editorial_from_post(request, purpose, activity=self.activity))
        if request.POST.get("action") == "publish":
            publish_activity_presentation(actor=request.user, presentation=presentation)
            messages.success(request, "Présentation publiée.")
        else:
            messages.success(request, "Présentation enregistrée en brouillon.")
        return redirect(f"{reverse('presentations:studio', kwargs={'activity_id': self.activity.pk})}?purpose={purpose}")


class ActivityPresentationPreviewView(ActivityPresentationAuthorityMixin, View):
    def get(self, request, *args, **kwargs):
        mode = request.GET.get("mode", "desktop")
        surface = PREVIEW_MODES.get(mode)
        if surface is None:
            raise Http404
        purpose = request.GET.get("purpose") or PresentationPurpose.PUBLIC_PAGE
        if purpose not in PresentationPurpose.values:
            raise Http404
        resolved = _preview_resolution(self.activity, purpose)
        context = build_activity_context(activity=self.activity, occurrence=_occurrence(self.activity), editorial=resolved.binding.editorial_data if resolved.binding else {}, primary_url=reverse("presentations:public-activity", kwargs={"activity_id": self.activity.pk}), primary_label="Ouvrir dans Makolo")
        html = render_presentation(manifest=resolved.manifest, theme_tokens=resolved.theme_tokens, context=context, surface=surface)
        return HttpResponse(_document(html, mode=mode, title=self.activity.title), content_type="text/html; charset=utf-8")


class PublicActivityPresentationView(View):
    def get(self, request, activity_id):
        activity = get_object_or_404(Activity.objects.select_related("space", "owner_profile"), pk=activity_id)
        if activity.visibility != ActivityVisibility.PUBLIC:
            raise Http404
        resolved = resolve_presentation(activity=activity, purpose=PresentationPurpose.PUBLIC_PAGE)
        context = build_activity_context(activity=activity, occurrence=_occurrence(activity), editorial=resolved.binding.editorial_data if resolved.binding else {})
        html = render_presentation(manifest=resolved.manifest, theme_tokens=resolved.theme_tokens, context=context, surface="web")
        return HttpResponse(_document(html, mode="desktop", title=activity.title), content_type="text/html; charset=utf-8")


class ParticipantAccessPresentationView(LoginRequiredMixin, View):
    login_url = "core:login"

    def get(self, request, access_id):
        access = get_object_or_404(participant_accesses_visible_to_buyer(request.user), pk=access_id)
        mode = request.GET.get("mode", "desktop")
        surface = PREVIEW_MODES.get(mode)
        if surface is None:
            raise Http404
        resolved = resolve_presentation(activity=access.activity, purpose=PresentationPurpose.ACCESS_PASS, occurrence=access.occurrence)
        vocabulary = vocabulary_for(activity=access.activity, workflow=getattr(access.journey, "workflow", None))
        context = build_access_context(access=access, editorial=resolved.binding.editorial_data if resolved.binding else {}, display_type=vocabulary.access_noun)
        html = render_presentation(manifest=resolved.manifest, theme_tokens=resolved.theme_tokens, context=context, surface=surface)
        return HttpResponse(_document(html, mode=mode, title=f"{vocabulary.access_noun} · {access.activity.title}"), content_type="text/html; charset=utf-8")


def _document(content, *, mode, title="Présentation Makolo"):
    frame_class = " mps-preview-frame-phone" if mode == "phone" else ""
    print_class = " mps-preview-print" if mode == "print" else ""
    return f'<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)}</title><link rel="stylesheet" href="/static/presentations/mps.css"></head><body class="mps-preview{print_class}"><div class="mps-preview-frame{frame_class}">{content}</div></body></html>'
