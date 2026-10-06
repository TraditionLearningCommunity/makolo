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
from presentations.product_language import vocabulary_for
from core.participant_selectors import participant_accesses_visible_to_buyer, participant_journeys
from journeys.models import WorkflowKind

from .asset_services import create_presentation_asset
from .catalog import catalog_entries, ensure_builtin_catalog
from .contexts import build_access_context, build_activity_context, build_journey_context
from .editorial import PURPOSE_FIELDS
from .enums import PresentationPurpose, Provenance, VersionStatus
from .models import PresentationTemplateVersion, PresentationThemeVersion
from .product_usage import ACTIVITY_OUTPUT_PURPOSES, access_presentation_purpose
from .rendering import render_presentation
from .resolver import ResolvedPresentation, resolve_presentation
from .selectors import available_template_versions, available_theme_versions
from .services import clear_activity_presentation, configure_activity_presentation, publish_activity_presentation

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


def _source_label(resource, *, actor, activity):
    if resource.provenance == Provenance.MAKOLO:
        return "Makolo"
    if resource.owner_profile_id == getattr(actor, "pk", None):
        return "Ma bibliothèque"
    if activity.space_id and resource.owner_space_id == activity.space_id:
        return "Espace"
    return "Communauté"


def _studio_usage(activity, purpose):
    if purpose == PresentationPurpose.PUBLIC_PAGE:
        if activity.visibility == ActivityVisibility.PUBLIC:
            return {
                "url": reverse("presentations:public-activity", kwargs={"activity_id": activity.pk}),
                "label": "Ouvrir la page présentée",
                "note": "Cette page est partageable publiquement.",
            }
        return {
            "url": "",
            "label": "",
            "note": "Prévisualisez ici. La page présentée ne devient publique que lorsque l’Activity elle-même est publique.",
        }
    if purpose in ACTIVITY_OUTPUT_PURPOSES:
        return {
            "url": reverse(
                "presentations:activity-artifact",
                kwargs={"activity_id": activity.pk, "purpose": purpose},
            ),
            "label": "Ouvrir cet artefact",
            "note": "Cet artefact reprend la visibilité de l’Activity.",
        }
    if purpose in {PresentationPurpose.ACCESS_PASS, PresentationPurpose.CONFIRMATION}:
        return {
            "url": "",
            "label": "",
            "note": "Ce choix s’applique automatiquement aux accès concernés lorsqu’ils sont réellement émis.",
        }
    if purpose == PresentationPurpose.BADGE:
        return {
            "url": "",
            "label": "",
            "note": "Présentation ne crée aucun badge. Ce style ne sera utilisé que lorsqu’un artefact badge canonique sera réellement relié.",
        }
    return {"url": "", "label": "", "note": ""}


class ActivityPresentationStudioView(ActivityPresentationAuthorityMixin, TemplateView):
    template_name = "presentations/studio.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        ensure_builtin_catalog(actor=self.request.user)
        purpose = self.request.GET.get("purpose") or PresentationPurpose.PUBLIC_PAGE
        if purpose not in PresentationPurpose.values:
            purpose = PresentationPurpose.PUBLIC_PAGE

        current = (
            self.activity.presentations.filter(occurrence__isnull=True, purpose=purpose)
            .select_related("template_version__template", "theme_version__theme")
            .first()
        )
        catalog = {item["slug"]: item for item in catalog_entries()}
        template_options = []
        for version in available_template_versions(
            actor=self.request.user,
            activity=self.activity,
            purpose=purpose,
        ):
            metadata = catalog.get(version.template.slug, {})
            template_options.append(
                {
                    "version": version,
                    "name": version.template.name,
                    "description": metadata.get("description") or version.template.description,
                    "category": metadata.get("category") or _source_label(
                        version.template,
                        actor=self.request.user,
                        activity=self.activity,
                    ),
                    "source": _source_label(
                        version.template,
                        actor=self.request.user,
                        activity=self.activity,
                    ),
                }
            )
        theme_options = [
            {
                "version": version,
                "name": version.theme.name,
                "source": _source_label(
                    version.theme,
                    actor=self.request.user,
                    activity=self.activity,
                ),
            }
            for version in available_theme_versions(
                actor=self.request.user,
                activity=self.activity,
            )
        ]
        editorial_fields = [
            {
                "name": field,
                "value": current.editorial_data.get(field, "") if current else "",
                "asset": field == "hero_image",
            }
            for field in PURPOSE_FIELDS.get(purpose, {})
        ]
        context.update(
            {
                "activity": self.activity,
                "purpose": purpose,
                "purposes": PresentationPurpose.choices,
                "template_options": template_options,
                "theme_options": theme_options,
                "current": current,
                "effective_source": (
                    "Configuration de cette Activity"
                    if current
                    else "Default de l’Espace"
                    if resolve_presentation(activity=self.activity, purpose=purpose).fallback_reason == "space-default"
                    else "Makolo Essential"
                ),
                "editorial_fields": editorial_fields,
                "usage": _studio_usage(self.activity, purpose),
                "library_url": reverse("presentations:library"),
                "space_library_url": (
                    reverse("presentations:space-library", kwargs={"slug": self.activity.space.slug})
                    if self.activity.space_id
                    else ""
                ),
            }
        )
        return context

    def post(self, request, *args, **kwargs):
        templates, themes = ensure_builtin_catalog(actor=request.user)
        purpose = request.POST.get("purpose") or PresentationPurpose.PUBLIC_PAGE
        if purpose not in PresentationPurpose.values:
            raise ValidationError("Usage de Présentation invalide.")
        if request.POST.get("action") == "use_default":
            clear_activity_presentation(
                actor=request.user,
                activity=self.activity,
                purpose=purpose,
            )
            messages.success(request, "Cette Activity utilise de nouveau le default disponible.")
            return redirect(
                f"{reverse('presentations:studio', kwargs={'activity_id': self.activity.pk})}?purpose={purpose}"
            )

        template_version_id = request.POST.get("template_version")
        theme_version_id = request.POST.get("theme_version")
        if template_version_id:
            template_version = get_object_or_404(
                PresentationTemplateVersion.objects.select_related("template"),
                pk=template_version_id,
            )
        else:
            template_slug = request.POST.get("template") or "makolo-essential"
            if template_slug not in templates:
                raise ValidationError("Modèle de Présentation invalide.")
            template_version = templates[template_slug]

        if theme_version_id:
            theme_version = get_object_or_404(
                PresentationThemeVersion.objects.select_related("theme"),
                pk=theme_version_id,
            )
        else:
            theme_slug = request.POST.get("theme") or "makolo-violet"
            if theme_slug not in themes:
                raise ValidationError("Thème de Présentation invalide.")
            theme_version = themes[theme_slug]

        presentation = configure_activity_presentation(
            actor=request.user,
            activity=self.activity,
            purpose=purpose,
            template_version=template_version,
            theme_version=theme_version,
            editorial_data=_editorial_from_post(
                request,
                purpose,
                activity=self.activity,
            ),
        )
        if request.POST.get("action") == "publish":
            publish_activity_presentation(actor=request.user, presentation=presentation)
            messages.success(request, "Présentation publiée.")
        else:
            messages.success(request, "Présentation enregistrée en brouillon.")
        return redirect(
            f"{reverse('presentations:studio', kwargs={'activity_id': self.activity.pk})}?purpose={purpose}"
        )


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
        public_url = (
            reverse("presentations:public-activity", kwargs={"activity_id": self.activity.pk})
            if self.activity.visibility == ActivityVisibility.PUBLIC
            else ""
        )
        context = build_activity_context(
            activity=self.activity,
            occurrence=_occurrence(self.activity),
            editorial=resolved.binding.editorial_data if resolved.binding else {},
            primary_url=public_url,
            primary_label="Ouvrir dans Makolo" if public_url else "",
        )
        html = render_presentation(manifest=resolved.manifest, theme_tokens=resolved.theme_tokens, context=context, surface=surface)
        return HttpResponse(_document(html, mode=mode, title=self.activity.title), content_type="text/html; charset=utf-8")


class ActivityArtifactPresentationView(View):
    def get(self, request, activity_id, purpose):
        if purpose not in ACTIVITY_OUTPUT_PURPOSES:
            raise Http404
        activity = get_object_or_404(
            Activity.objects.select_related("space", "owner_profile"),
            pk=activity_id,
        )
        public = activity.visibility == ActivityVisibility.PUBLIC
        authorized = request.user.is_authenticated and can(
            request.user,
            PermissionCode.ACTIVITY_MANAGE,
            activity=activity,
        )
        if not public and not authorized:
            raise Http404

        resolved = resolve_presentation(activity=activity, purpose=purpose)
        public_url = (
            reverse("presentations:public-activity", kwargs={"activity_id": activity.pk})
            if public
            else ""
        )
        context = build_activity_context(
            activity=activity,
            occurrence=_occurrence(activity),
            editorial=resolved.binding.editorial_data if resolved.binding else {},
            primary_url=public_url,
            primary_label="Voir l’activité" if public_url else "",
        )
        label = dict(PresentationPurpose.choices)[purpose]
        html = render_presentation(
            manifest=resolved.manifest,
            theme_tokens=resolved.theme_tokens,
            context=context,
            surface="web",
        )
        response = HttpResponse(
            _document(html, mode="desktop", title=f"{label} · {activity.title}"),
            content_type="text/html; charset=utf-8",
        )
        if not public:
            response["Cache-Control"] = "private, no-store"
        return response


class PublicActivityPresentationView(View):
    def get(self, request, activity_id):
        activity = get_object_or_404(Activity.objects.select_related("space", "owner_profile"), pk=activity_id)
        if activity.visibility != ActivityVisibility.PUBLIC:
            raise Http404
        resolved = resolve_presentation(activity=activity, purpose=PresentationPurpose.PUBLIC_PAGE)
        context = build_activity_context(activity=activity, occurrence=_occurrence(activity), editorial=resolved.binding.editorial_data if resolved.binding else {})
        html = render_presentation(manifest=resolved.manifest, theme_tokens=resolved.theme_tokens, context=context, surface="web")
        return HttpResponse(_document(html, mode="desktop", title=activity.title), content_type="text/html; charset=utf-8")


class ParticipantJourneyPresentationView(LoginRequiredMixin, View):
    login_url = "core:login"

    def get(self, request, journey_id):
        journey = get_object_or_404(
            participant_journeys(request.user).select_related(
                "activity",
                "activity__space",
                "activity__owner_profile",
                "occurrence",
                "beneficiary",
                "external_beneficiary",
            ),
            pk=journey_id,
        )
        if journey.workflow != WorkflowKind.INVITATION:
            raise Http404
        resolved = resolve_presentation(
            activity=journey.activity,
            occurrence=journey.occurrence,
            purpose=PresentationPurpose.INVITATION,
        )
        context = build_journey_context(
            journey=journey,
            editorial=resolved.binding.editorial_data if resolved.binding else {},
            primary_url=reverse(
                "core:participant-journey-detail",
                kwargs={"pk": journey.pk},
            ),
            primary_label="Répondre dans Makolo",
        )
        html = render_presentation(
            manifest=resolved.manifest,
            theme_tokens=resolved.theme_tokens,
            context=context,
            surface="web",
        )
        response = HttpResponse(
            _document(
                html,
                mode="desktop",
                title=f"Invitation · {journey.activity.title}",
            ),
            content_type="text/html; charset=utf-8",
        )
        response["Cache-Control"] = "private, no-store"
        return response


class ParticipantAccessPresentationView(LoginRequiredMixin, View):
    login_url = "core:login"

    def get(self, request, access_id):
        access = get_object_or_404(participant_accesses_visible_to_buyer(request.user), pk=access_id)
        mode = request.GET.get("mode", "desktop")
        surface = PREVIEW_MODES.get(mode)
        if surface is None:
            raise Http404
        purpose = access_presentation_purpose(access)
        resolved = resolve_presentation(activity=access.activity, purpose=purpose, occurrence=access.occurrence)
        vocabulary = vocabulary_for(activity=access.activity, workflow=getattr(access.journey, "workflow", None))
        context = build_access_context(access=access, editorial=resolved.binding.editorial_data if resolved.binding else {}, display_type=vocabulary.access_noun)
        html = render_presentation(manifest=resolved.manifest, theme_tokens=resolved.theme_tokens, context=context, surface=surface)
        return HttpResponse(_document(html, mode=mode, title=f"{vocabulary.access_noun} · {access.activity.title}"), content_type="text/html; charset=utf-8")


def _document(content, *, mode, title="Présentation Makolo"):
    frame_class = " mps-preview-frame-phone" if mode == "phone" else ""
    print_class = " mps-preview-print" if mode == "print" else ""
    return f'<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)}</title><link rel="stylesheet" href="/static/presentations/mps.css"></head><body class="mps-preview{print_class}"><div class="mps-preview-frame{frame_class}">{content}</div></body></html>'
