from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from activities.models import ActivityStatus, ActivityVisibility
from social.models import ActionNeed, ActionNeedCandidateKind, ActionNeedIntakePolicy, ActionNeedStatus, ActionNeedVisibility
from topics.models import ActionMatchKind

from .selectors import funding_progress
from .services import create_funding


User = get_user_model()


class FundingViewTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(email="funding-view-owner@example.test", username="funding-view-owner", password="test-pass")
        self.contributor = User.objects.create_user(email="funding-view-contributor@example.test", username="funding-view-contributor", password="test-pass")
        self.funding = create_funding(
            actor=self.owner,
            title="Réunir le budget transport",
            short_description="Rendre le déplacement possible.",
            currency="USD",
            target_amount=Decimal("100.00"),
            status=ActivityStatus.PUBLISHED,
            visibility=ActivityVisibility.PUBLIC,
        )

    def test_public_detail_uses_funding_language_and_progress(self):
        response = self.client.get(reverse("funding:detail", args=[self.funding.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Objectif")
        self.assertContains(response, "Réuni")
        self.assertContains(response, "Reste à réunir")
        self.assertNotContains(response, "-100")

    def test_contribute_creates_canonical_obligation_and_redirects_to_payments(self):
        self.client.force_login(self.contributor)
        response = self.client.post(
            reverse("funding:contribute", args=[self.funding.pk]),
            {"amount": "25.00", "client_reference": "view-test-1"},
        )
        self.assertEqual(response.status_code, 302)
        contribution = self.funding.contributions.get(contributor_profile=self.contributor)
        self.assertIsNotNone(contribution.payment_obligation_id)
        self.assertEqual(
            response.url,
            reverse("payments:obligation-start", kwargs={"obligation_pk": contribution.payment_obligation_id}),
        )
        self.assertEqual(funding_progress(self.funding).raised_amount, Decimal("0.00"))

    def test_only_explicit_open_public_need_is_presented_as_help(self):
        ActionNeed.objects.create(
            owner_profile=self.owner,
            created_by=self.owner,
            title="Cherche deux bénévoles",
            match_kind=ActionMatchKind.VOLUNTEER,
            candidate_kind=ActionNeedCandidateKind.PROFILE,
            activity=self.funding.activity,
            visibility=ActionNeedVisibility.PUBLIC,
            intake_policy=ActionNeedIntakePolicy.OPEN,
            status=ActionNeedStatus.OPEN,
        )
        ActionNeed.objects.create(
            owner_profile=self.owner,
            created_by=self.owner,
            title="Besoin privé",
            match_kind=ActionMatchKind.PARTNER,
            candidate_kind=ActionNeedCandidateKind.PROFILE,
            activity=self.funding.activity,
            visibility=ActionNeedVisibility.PRIVATE,
            intake_policy=ActionNeedIntakePolicy.INVITE_ONLY,
            status=ActionNeedStatus.OPEN,
        )
        response = self.client.get(reverse("funding:detail", args=[self.funding.pk]))
        self.assertContains(response, "Cherche deux bénévoles")
        self.assertNotContains(response, "Besoin privé")

    def test_private_or_draft_funding_is_not_public(self):
        self.funding.activity.visibility = ActivityVisibility.PRIVATE
        self.funding.activity.save(update_fields=["visibility", "updated_at"])
        response = self.client.get(reverse("funding:detail", args=[self.funding.pk]))
        self.assertEqual(response.status_code, 404)
