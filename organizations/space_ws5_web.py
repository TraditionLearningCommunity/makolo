from __future__ import annotations

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views import View

from access.models import AccessUseResult
from access.services import resolve_access_credential, validate_access
from activities.models import Occurrence
from journeys.models import Journey
from operations.occurrence_experience import resolve_occurrence_experience
from activities.services import set_occurrence_live_enabled
from authorization.constants import PermissionCode
from authorization.services import can
from scanner.permissions import user_can_scan_activity
from scanner.occurrence_access import control_occurrence_access
from scanner.space_context import build_scanner_context

from .api.space_mark_projection import orchestrate_space_mark
from .console_scanner import _accepted_at, _scanner_message
from .space_web_views import SpaceWebMixin


@method_decorator(never_cache, name='dispatch')
class _SpaceOccurrenceWebMixin(SpaceWebMixin):
    """Occurrence-scoped Space depth that keeps WS1 authority/context semantics."""

    def get_occurrence(self):
        if hasattr(self, "_occurrence"):
            return self._occurrence
        occurrence = get_object_or_404(
            Occurrence.objects.select_related("activity", "activity__space")
            .prefetch_related("place_links__place"),
            pk=self.kwargs["occurrence_id"],
        )
        if occurrence.activity.space_id != self.space.pk and not Journey.objects.filter(
            occurrence=occurrence,
            activity=occurrence.activity,
            beneficiary_space=self.space,
        ).exists():
            raise Http404
        # Viewing a beneficiary Space Journey requires a current user mandate;
        # the experience resolver (and mutation owners) recheck that authority.
        self._occurrence = occurrence
        return occurrence

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        occurrence = self.get_occurrence()
        context.update(
            {
                "occurrence": occurrence,
                "activity": occurrence.activity,
                "day_of_url": reverse(
                    "organizations:space-occurrence-day-of",
                    kwargs={"slug": self.space.slug, "occurrence_id": occurrence.pk},
                ),
                "live_url": reverse(
                    "organizations:space-occurrence-live",
                    kwargs={"slug": self.space.slug, "occurrence_id": occurrence.pk},
                ),
                "scanner_url": reverse(
                    "organizations:space-occurrence-scanner",
                    kwargs={"slug": self.space.slug, "occurrence_id": occurrence.pk},
                ),
            }
        )
        return context


class SpaceOccurrenceDayOfView(_SpaceOccurrenceWebMixin):
    template_name = "organizations/space/day_of.html"
    space_nav_key = ""
    space_page_title = "Jour J"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        occurrence = self.get_occurrence()
        projection = resolve_occurrence_experience(
            occurrence=occurrence,
            viewer=self.request.user,
            surface="day_of",
            observed_at=timezone.now(),
            actor_space_id=self.space.pk,
        )
        if projection is None:
            raise Http404
        context["projection"] = projection
        context["can_configure_live"] = (
            can(self.request.user, PermissionCode.ACTIVITY_MANAGE,
                activity=occurrence.activity, include_platform=False)
            or bool(
                occurrence.activity.space_id == self.space.pk
                and can(self.request.user, PermissionCode.SPACE_ACTIVITIES_MANAGE,
                        self.space, include_platform=False)
            )
        )
        return context

    def post(self, request, *args, **kwargs):
        # HTML form is a presentation handoff; the domain service rechecks
        # canonical authority, including when this request bypasses the form.
        if request.POST.get("action") != "configure_live":
            raise Http404
        enabled = request.POST.get("enabled")
        if enabled not in {"0", "1"}:
            raise Http404
        set_occurrence_live_enabled(
            occurrence=self.get_occurrence(),
            actor=request.user,
            enabled=enabled == "1",
        )
        return redirect(
            "organizations:space-occurrence-day-of",
            slug=self.space.slug,
            occurrence_id=self.get_occurrence().pk,
        )


class SpaceOccurrenceLiveView(_SpaceOccurrenceWebMixin):
    template_name = "organizations/space/live.html"
    space_nav_key = ""
    space_page_title = "Makolo Live"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        now = timezone.now()
        projection = resolve_occurrence_experience(
            occurrence=self.get_occurrence(),
            viewer=self.request.user,
            surface="live",
            observed_at=now,
            actor_space_id=self.space.pk,
        )
        if projection is None:
            raise Http404
        context["projection"] = projection
        context["generated_at"] = now
        return context


class SpaceOccurrenceDepthView(_SpaceOccurrenceWebMixin):
    """One owner-backed depth for a Space actor, not another role-mode page."""
    template_name = "organizations/space/depth.html"
    space_nav_key = ""
    space_page_title = "Profondeur Jour J"

    def get_context_data(self, **kwargs):
        from operations.occurrence_web_depth import depth_page

        context = super().get_context_data(**kwargs)
        occurrence = self.get_occurrence()
        projection = resolve_occurrence_experience(
            occurrence=occurrence,
            viewer=self.request.user,
            surface="day_of", observed_at=timezone.now(),
            actor_space_id=self.space.pk,
        )
        if projection is None:
            raise Http404
        kind = self.kwargs["kind"]
        context["projection"] = projection
        context.update(depth_page(
            occurrence=occurrence, actor=self.request.user,
            projection=projection, kind=kind,
        ))
        context["depth_kind"] = kind
        return context

    def post(self, request, *args, **kwargs):
        from django.contrib import messages
        from operations.occurrence_web_depth import execute_depth_action

        occurrence = self.get_occurrence()
        projection = resolve_occurrence_experience(
            occurrence=occurrence, viewer=request.user,
            surface="day_of", observed_at=timezone.now(),
            actor_space_id=self.space.pk,
        )
        if projection is None:
            raise Http404
        kind = self.kwargs["kind"]
        try:
            execute_depth_action(
                occurrence=occurrence, actor=request.user,
                projection=projection, kind=kind, submitted=request.POST,
            )
            messages.success(request, "Opération confirmée par le propriétaire.")
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
        return redirect(
            "organizations:space-occurrence-depth",
            slug=self.space.slug, occurrence_id=occurrence.pk, kind=kind,
        )


class SpaceOccurrenceScannerView(_SpaceOccurrenceWebMixin):
    template_name = "organizations/space/scanner.html"
    space_nav_key = ""
    space_page_title = "Scanner"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.get_occurrence().activity.space_id != self.space.pk:
            # A beneficiary Space may consult its Journey, but does not gain
            # control of the provider's admission checkpoint in this context.
            raise Http404
        scanner = build_scanner_context(
            occurrence=self.get_occurrence(),
            actor=self.request.user,
            observed_at=timezone.now(),
        )
        if scanner is None:
            raise Http404
        context["projection"] = scanner
        context["scanner_available"] = "scan" in scanner.get("capabilities", ())
        context["scan_action_url"] = reverse(
            "organizations:space-occurrence-scanner-action",
            kwargs={
                "slug": self.space.slug,
                "occurrence_id": self.get_occurrence().pk,
            },
        )
        return context


class SpaceOccurrenceScannerActionView(_SpaceOccurrenceWebMixin, View):
    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        occurrence = self.get_occurrence()
        if occurrence.activity.space_id != self.space.pk:
            raise Http404
        if not user_can_scan_activity(
            request.user, occurrence.activity, occurrence=occurrence
        ):
            raise Http404
        token = (request.POST.get("token") or "").strip()
        client_reference = (request.POST.get("client_reference") or "").strip()
        if not token:
            return JsonResponse({
                "accepted": False,
                "result": AccessUseResult.INVALID_CREDENTIAL,
                "message": "QR invalide ou non reconnu.",
            }, status=400)
        try:
            outcome = control_occurrence_access(
                occurrence=occurrence,
                actor=request.user,
                token=token,
                client_reference=client_reference,
            )
        except DjangoPermissionDenied:
            raise Http404
        except ValidationError:
            return JsonResponse({
                "accepted": False,
                "result": AccessUseResult.INVALID_CREDENTIAL,
                "message": "QR invalide ou non reconnu.",
            }, status=400)
        response = JsonResponse(outcome)
        response["Cache-Control"] = "private, no-store"
        return response


@method_decorator(never_cache, name="dispatch")
class SpaceMarkWS5View(SpaceWebMixin):
    template_name = "organizations/space/mark_ws5.html"
    space_nav_key = "mark"
    space_page_title = "Makolo Mark"

    def _mark_context(self):
        context = {"responsibility": self.selected_responsibility["key"]}
        occurrence_id = (
            self.request.POST.get("occurrence_id")
            or self.request.GET.get("occurrence")
            or ""
        ).strip()
        if occurrence_id:
            context["occurrence_id"] = occurrence_id

        email = (self.request.POST.get("team_member_email") or "").strip()
        role = (self.request.POST.get("team_member_role") or "").strip()
        if email or role:
            context["team_member"] = {"email": email, "role": role}

        confirm_code = (self.request.POST.get("confirm_code") or "").strip()
        if confirm_code:
            context["confirmation"] = {
                "code": confirm_code,
                "email": (self.request.POST.get("confirm_email") or "").strip(),
                "role": (self.request.POST.get("confirm_role") or "").strip(),
            }
        return context

    def post(self, request, *args, **kwargs):
        value = (request.POST.get("value") or "").strip()
        if request.POST.get("cancel_confirmation"):
            return self.render_to_response(self.get_context_data(mark_value=value))
        if not value or len(value) > 600:
            message = (
                "Dites simplement ce que vous voulez faire."
                if not value
                else "Votre demande doit contenir au maximum 600 caractères."
            )
            return self.render_to_response(
                self.get_context_data(mark_value=value, mark_error=message),
                status=400,
            )
        result = orchestrate_space_mark(
            profile=request.user,
            space=self.space,
            input_kind="text",
            value=value,
            context=self._mark_context(),
            observed_at=timezone.now(),
        )
        context = self.get_context_data()
        context["mark_value"] = value
        context["mark_result"] = result
        context["mark_handoff_url"] = self._handoff_url(result)
        return self.render_to_response(context)

    def _handoff_url(self, result):
        handoff = result.get("handoff") or {}
        payload = result.get("result") or {}
        identity = payload.get("identity") or {}
        occurrence_id = identity.get("id")
        if occurrence_id and handoff.get("owner") == "operations":
            return reverse(
                "organizations:space-occurrence-day-of",
                kwargs={"slug": self.space.slug, "occurrence_id": occurrence_id},
            )
        if occurrence_id and handoff.get("owner") == "scanner":
            return reverse(
                "organizations:space-occurrence-scanner",
                kwargs={"slug": self.space.slug, "occurrence_id": occurrence_id},
            )
        if handoff.get("owner") == "organizations" and handoff.get("surface") == "team":
            return reverse("organizations:console-team", kwargs={"slug": self.space.slug})
        return ""
