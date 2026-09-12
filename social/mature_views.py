from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse
from django.views.generic import TemplateView

from discovery.recommendations import activity_destination

from .models import ActionProposalDirection, ActionProposalStatus
from .profile_search import action_proposals_requiring_actor_response, proposals_for_profile


class MatureProfileSolicitationsView(LoginRequiredMixin, TemplateView):
    """Action inbox using the canonical authority-aware pending selector.

    Historical Profile-targeted rows are retained for compatibility, while live
    Profile, Space and owner-side proposals come from the same selector Home uses.
    Mutations continue to revalidate authority in respond_to_action_proposal().
    """

    template_name = "social/profile_solicitations.html"
    login_url = "core:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        pending = list(action_proposals_requiring_actor_response(self.request.user))
        pending_ids = {proposal.pk for proposal in pending}
        history = list(
            proposals_for_profile(self.request.user)
            .exclude(pk__in=pending_ids)
            .order_by("-created_at", "id")[:100]
        )
        proposals = pending + history
        for proposal in proposals:
            proposal.continuation_label = ""
            proposal.continuation_url = ""
            proposal.response_context_label = "Pour vous"
            proposal.response_context_detail = "Vous répondez en votre nom."

            response_space = None
            if proposal.direction == ActionProposalDirection.OWNER_TO_CANDIDATE and proposal.candidate_space_id:
                response_space = proposal.candidate_space
            elif proposal.direction == ActionProposalDirection.CANDIDATE_TO_OWNER and proposal.need.space_id:
                response_space = proposal.need.space
            if response_space is not None:
                proposal.response_context_label = f"Pour {response_space.name}"
                proposal.response_context_detail = f"Vous répondez au nom de {response_space.name}, dans votre autorité actuelle."

            if proposal.status == ActionProposalStatus.ACCEPTED:
                if proposal.need.opportunity_id:
                    proposal.continuation_label = "Voir l’Opportunity"
                    proposal.continuation_url = reverse(
                        "opportunities:detail",
                        kwargs={"pk": proposal.need.opportunity_id},
                    )
                elif proposal.need.activity_id:
                    proposal.continuation_label, proposal.continuation_url = activity_destination(
                        proposal.need.activity
                    )
        context["solicitations"] = proposals
        context["proposals"] = proposals
        return context
