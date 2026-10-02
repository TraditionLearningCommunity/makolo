from __future__ import annotations

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views import View

from access.models import AccessUseResult
from access.services import resolve_access_credential, validate_access
from activities.models import Occurrence
from operations.occurrence_live import resolve_occurrence_live
from operations.space_day_of import build_space_operator_day_of
from scanner.permissions import user_can_scan_activity
from scanner.space_context import build_scanner_context

from .api.space_mark_projection import orchestrate_space_mark
from .console_scanner import _accepted_at, _scanner_message
from .space_web_views import SpaceWebMixin


class _SpaceOccurrenceWebMixin(SpaceWebMixin):
    """Occurrence-scoped Space depth that keeps WS1 authority/context semantics."""

    def get_occurrence(self):
        if hasattr(self, "_occurrence"):
            return self._occurrence
        occurrence = get_object_or_404(
            Occurrence.objects.select_related("activity", "activity__space"),
            pk=self.kwargs["occurrence_id"],
            activity__space=self.space,
        )
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
        projection = build_space_operator_day_of(
            occurrence=self.get_occurrence(),
            actor=self.request.user,
            observed_at=timezone.now(),
        )
        if projection is None:
            raise Http404
        context["projection"] = projection
        return context


class SpaceOccurrenceLiveView(_SpaceOccurrenceWebMixin):
    template_name = "organizations/space/live.html"
    space_nav_key = ""
    space_page_title = "Live"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        generated_at = timezone.now()
        projection = resolve_occurrence_live(
            occurrence=self.get_occurrence(),
            actor=self.request.user,
            observed_at=generated_at,
        )
        if projection is None or projection.get("perspective") not in {"space", "operator"}:
            raise Http404
        context["projection"] = projection
        context["generated_at"] = generated_at
        return context


class SpaceOccurrenceScannerView(_SpaceOccurrenceWebMixin):
    template_name = "organizations/space/scanner.html"
    space_nav_key = ""
    space_page_title = "Scanner"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
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
        activity = occurrence.activity

        # Capability GETs are advisory. Revalidate canonical authority at mutation time.
        if not user_can_scan_activity(request.user, activity, occurrence=occurrence):
            raise Http404

        scanner = build_scanner_context(
            occurrence=occurrence,
            actor=request.user,
            observed_at=timezone.now(),
        )
        if scanner is None or "scan" not in scanner.get("capabilities", ()):
            return JsonResponse(
                {
                    "accepted": False,
                    "result": "unavailable",
                    "message": "Le scan n’est pas disponible pour cette Occurrence.",
                },
                status=409,
            )

        token = (request.POST.get("token") or "").strip()
        client_reference = (request.POST.get("client_reference") or "").strip()[:64]
        if not token:
            return JsonResponse(
                {
                    "accepted": False,
                    "result": AccessUseResult.INVALID_CREDENTIAL,
                    "message": "QR invalide ou non reconnu.",
                },
                status=400,
            )

        try:
            credential = resolve_access_credential(token)
            outcome = validate_access(
                access=credential.access,
                credential=credential,
                controller=request.user,
                authority_check=lambda actor, access: user_can_scan_activity(
                    actor,
                    access.activity,
                    occurrence=occurrence,
                ),
                expected_activity=activity,
                expected_occurrence=occurrence,
                source="space_ws5",
                client_reference=client_reference,
            )
        except DjangoPermissionDenied:
            raise Http404
        except ValidationError:
            return JsonResponse(
                {
                    "accepted": False,
                    "result": AccessUseResult.INVALID_CREDENTIAL,
                    "message": "QR invalide ou non reconnu.",
                },
                status=400,
            )

        accepted_at = _accepted_at(outcome.access)
        return JsonResponse(
            {
                "accepted": outcome.accepted,
                "result": outcome.result,
                "message": _scanner_message(outcome, activity),
                "controlled_at": outcome.use.used_at.isoformat() if outcome.use else None,
                "accepted_at": accepted_at.isoformat() if accepted_at else None,
                "valid_from": (
                    outcome.access.valid_from.isoformat()
                    if outcome.access and outcome.access.valid_from
                    else None
                ),
                "access": (
                    {
                        "beneficiary": (
                            outcome.access.beneficiary.full_name
                            or "Bénéficiaire"
                        ),
                        "status": outcome.access.status,
                    }
                    if outcome.access
                    else None
                ),
            }
        )


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
