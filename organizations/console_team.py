from django.views.generic import TemplateView

from .console_selectors import team_for_console, teams_for_console
from .console_views import SpaceConsoleMixin


class SpaceConsoleTeamView(SpaceConsoleMixin, TemplateView):
    """Operational Team surface; authority remains exclusively Mandate-based."""

    template_name = "organizations/console/team.html"
    module_key = "team"
    page_title = "Équipe"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = (self.request.GET.get("q") or "").strip()
        memberships = team_for_console(self.space_console, query=query)
        context.update(
            {
                "teams": teams_for_console(self.space_console),
                "page_obj": self.paginate(memberships, per_page=30),
                "memberships": memberships,
                "query": query,
                "can_manage_team": self.space_console.can_manage_team,
            }
        )
        return context