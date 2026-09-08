from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from django.views.generic import TemplateView

from activities.selectors import activities_owned_by

from .home_presentation import build_mature_home
from .participant_selectors import (
    participant_actionable_journeys,
    participant_active_accesses,
    participant_upcoming_engagements,
)
from .participant_views import HOME_SECTION_LIMIT, _access_card, _journey_card, _recent_history_items


class MatureParticipantHomeView(LoginRequiredMixin, TemplateView):
    template_name = "core/participant_home.html"
    login_url = "core:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile = self.request.user
        now = timezone.now()
        home = build_mature_home(profile, observed_at=now)

        # Keep the established personal-hub context contract for downstream
        # templates/tests while M8-A makes ``home`` the only rendered ranking.
        # These compatibility projections use owner selectors and do not create
        # a second readiness/priority engine.
        upcoming = list(participant_upcoming_engagements(profile, at=now)[:HOME_SECTION_LIMIT])
        actionable = list(participant_actionable_journeys(profile)[:HOME_SECTION_LIMIT])
        context.update(
            {
                "home": home,
                "actionable": [_journey_card(journey) for journey in actionable],
                "upcoming": [_access_card(access) for access in upcoming],
                "active_access_count": participant_active_accesses(profile, at=now).count(),
                "recent_history": _recent_history_items(profile, at=now),
                "organized_activities": list(activities_owned_by(profile)[:HOME_SECTION_LIMIT]),
            }
        )
        return context
