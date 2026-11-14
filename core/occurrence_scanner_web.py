"""Personal-Activity scanner entry using the same canonical AccessUse owner."""
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.generic import TemplateView
from django.utils import timezone

from activities.models import Occurrence
from scanner.occurrence_access import control_occurrence_access
from scanner.permissions import user_can_scan_activity
from scanner.space_context import build_scanner_context


@method_decorator(never_cache, name='dispatch')
class PersonalOccurrenceScannerView(LoginRequiredMixin, TemplateView):
    template_name = "core/occurrence_scanner.html"
    login_url = "core:login"

    def _occurrence(self):
        return get_object_or_404(
            Occurrence.objects.select_related("activity", "activity__space"),
            pk=self.kwargs["pk"],
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        occurrence = self._occurrence()
        if not user_can_scan_activity(
            self.request.user, occurrence.activity, occurrence=occurrence,
        ):
            raise Http404
        scanner = build_scanner_context(
            occurrence=occurrence, actor=self.request.user,
            observed_at=timezone.now(),
        )
        if scanner is None:
            raise Http404
        context.update({
            "occurrence": occurrence,
            "activity": occurrence.activity,
            "scanner_available": "scan" in scanner["capabilities"],
            "scan_action_url": reverse(
                "core:participant-occurrence-scanner",
                kwargs={"pk": occurrence.pk},
            ),
            "day_of_url": reverse(
                "core:participant-occurrence-day-of",
                kwargs={"pk": occurrence.pk},
            ),
        })
        return context

    def post(self, request, *args, **kwargs):
        occurrence = self._occurrence()
        if not user_can_scan_activity(
            request.user, occurrence.activity, occurrence=occurrence,
        ):
            raise Http404
        try:
            result = control_occurrence_access(
                occurrence=occurrence,
                actor=request.user,
                token=(request.POST.get("token") or "").strip(),
                client_reference=(request.POST.get("client_reference") or "").strip(),
            )
        except DjangoPermissionDenied:
            raise Http404
        except ValidationError:
            return JsonResponse({
                "accepted": False,
                "result": "invalid_credential",
                "message": "QR invalide ou non reconnu.",
            }, status=400)
        response = JsonResponse(result)
        response["Cache-Control"] = "private, no-store"
        return response
