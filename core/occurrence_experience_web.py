"""Canonical Web Jour J and Live for an authenticated Profile.

The same page content is used inside the Space shell. Business responsibilities
coexist according to owner-backed server authorization, not a role selector.
"""
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.generic import TemplateView

from activities.models import Occurrence
from activities.services import set_occurrence_live_enabled
from authorization.constants import PermissionCode
from authorization.services import can
from operations.occurrence_experience import resolve_occurrence_experience


class _PersonalOccurrenceExperienceView(LoginRequiredMixin, TemplateView):
    login_url = "core:login"
    surface = None

    def get_occurrence(self):
        if not hasattr(self, "_occurrence"):
            self._occurrence = get_object_or_404(
                Occurrence.objects.select_related("activity", "activity__space")
                .prefetch_related("place_links__place"),
                pk=self.kwargs["pk"],
            )
        return self._occurrence

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        occurrence = self.get_occurrence()
        now = timezone.now()
        projection = resolve_occurrence_experience(
            occurrence=occurrence,
            viewer=self.request.user,
            surface=self.surface,
            observed_at=now,
        )
        if projection is None:
            raise Http404
        context.update({
            "occurrence": occurrence,
            "activity": occurrence.activity,
            "projection": projection,
            "generated_at": now,
            "day_of_url": reverse(
                "core:participant-occurrence-day-of", kwargs={"pk": occurrence.pk},
            ),
            "live_url": reverse(
                "core:participant-occurrence-live", kwargs={"pk": occurrence.pk},
            ),
            "can_configure_live": (
                can(self.request.user, PermissionCode.ACTIVITY_MANAGE,
                    activity=occurrence.activity, include_platform=False)
                or bool(occurrence.activity.space_id and can(
                    self.request.user, PermissionCode.SPACE_ACTIVITIES_MANAGE,
                    occurrence.activity.space, include_platform=False,
                ))
            ),
            "space_work_url": None,
            "scanner_url": None,
        })
        return context


class PersonalOccurrenceDayOfView(_PersonalOccurrenceExperienceView):
    template_name = "core/occurrence_day_of.html"
    surface = "day_of"

    def post(self, request, *args, **kwargs):
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
        return redirect("core:participant-occurrence-day-of", pk=self.get_occurrence().pk)


class PersonalOccurrenceLiveView(_PersonalOccurrenceExperienceView):
    template_name = "core/occurrence_live.html"
    surface = "live"
