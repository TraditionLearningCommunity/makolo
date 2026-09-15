from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import UserProfile
from conversations.contact_services import ensure_proposal_conversation
from social.bilateral_services import (
    create_action_need,
    create_action_proposal,
    respond_to_action_proposal,
)
from social.models import ActionProposalStatus
from topics.models import ActionMatchKind, ProfileOpenTo


User = get_user_model()
PASSWORD = "Strong-M9D-Password-2026!"


def make_profile_user(username):
    user = User.objects.create_user(
        username=username,
        email=f"{username}@example.test",
        password=PASSWORD,
    )
    UserProfile.objects.create(
        user=user,
        city="Lubumbashi",
        country="RDC",
        public_profile=True,
        searchable=True,
    )
    return user


class M9DActionNetworkConversationTests(TestCase):
    def setUp(self):
        self.owner = make_profile_user("m9d-owner")
        self.candidate = make_profile_user("m9d-candidate")
        self.outsider = make_profile_user("m9d-outsider")
        ProfileOpenTo.objects.create(
            profile=self.candidate,
            kind=ActionMatchKind.MENTOR,
            is_active=True,
            is_searchable=True,
        )
        self.need = create_action_need(
            actor=self.owner,
            owner_profile=self.owner,
            title="Mentorat M9-D",
            match_kind=ActionMatchKind.MENTOR,
        )
        self.proposal = create_action_proposal(
            actor=self.owner,
            need=self.need,
            candidate_profile=self.candidate,
            message="Coordonnons le mentorat dans son contexte Makolo.",
        )
        respond_to_action_proposal(
            actor=self.candidate,
            proposal=self.proposal,
            status=ActionProposalStatus.ACCEPTED,
        )
        self.proposal.refresh_from_db()

    def test_accepted_action_proposal_converges_to_one_contextual_conversation(self):
        first = ensure_proposal_conversation(actor=self.owner, proposal=self.proposal)
        second = ensure_proposal_conversation(actor=self.candidate, proposal=self.proposal)

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(first.context.action_proposal_id, self.proposal.pk)

        self.client.force_login(self.owner)
        response = self.client.get(reverse("conversations:detail", kwargs={"pk": first.pk}))
        self.assertEqual(response.status_code, 200)

        self.client.force_login(self.candidate)
        response = self.client.get(reverse("conversations:detail", kwargs={"pk": first.pk}))
        self.assertEqual(response.status_code, 200)

        self.client.force_login(self.outsider)
        response = self.client.get(reverse("conversations:detail", kwargs={"pk": first.pk}))
        self.assertEqual(response.status_code, 403)
        self.assertNotContains(response, "Mentorat M9-D", status_code=403)
