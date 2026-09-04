from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View

from topics.models import ProfileInterest
from topics.services import replace_profile_interests


DISCOVER_PROMPT_SESSION_KEY = "g8_discover_interests_prompt_dismissed"


def _safe_next(request):
    value = (request.POST.get("next") or "").strip()
    if value and url_has_allowed_host_and_scheme(
        value,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return value
    return reverse("discovery:home")


class ProfileInterestQuickCaptureView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request):
        next_url = _safe_next(request)
        # The compact Discover capture is intentionally only for Profiles with
        # no existing Interests. A concurrent/full settings edit must never be
        # overwritten by this shortcut.
        if ProfileInterest.objects.filter(profile=request.user).exists():
            return redirect(next_url)

        topic_ids = request.POST.getlist("topics")
        if not topic_ids:
            messages.info(request, "Choisissez au moins un sujet, ou fermez cette suggestion pour cette session.")
            return redirect(next_url)
        try:
            replace_profile_interests(profile=request.user, topic_ids=topic_ids)
        except ValidationError:
            messages.error(request, "Un des sujets choisis n’est plus disponible. Réessayez.")
            return redirect(next_url)

        request.session[DISCOVER_PROMPT_SESSION_KEY] = True
        messages.success(request, "Vos centres d’intérêt ont été enregistrés pour personnaliser Discover.")
        return redirect(next_url)


class DismissProfileInterestPromptView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request):
        request.session[DISCOVER_PROMPT_SESSION_KEY] = True
        return redirect(_safe_next(request))
