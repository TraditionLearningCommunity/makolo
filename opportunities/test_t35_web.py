from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import OpportunityKind, OpportunityPublicationStatus, OpportunitySave, OpportunitySourceType, OpportunitySubmission
from .services import create_opportunity, create_opportunity_revision, create_opportunity_source, publish_opportunity_revision


User = get_user_model()


class OpportunityParticipantWebTests(TestCase):
    def setUp(self):
        self.curator = User.objects.create_superuser(username="t35-curator", email="t35-curator@example.test", password="x")
        self.user = User.objects.create_user(username="t35-participant", email="t35-participant@example.test", password="x")
        self.other = User.objects.create_user(username="t35-other", email="t35-other@example.test", password="x")
        self.published = self._opportunity("Opportunity publique", published=True)
        self.draft = self._opportunity("Opportunity brouillon", published=False)

    def _opportunity(self, title, *, published):
        opportunity = create_opportunity(actor=self.curator, kind=OpportunityKind.JOB)
        revision = create_opportunity_revision(opportunity=opportunity, actor=self.curator, title=title, issuer_name="Entreprise fictive", summary="Une opportunité de démonstration", remote_allowed=True)
        create_opportunity_source(opportunity=opportunity, actor=self.curator, source_type=OpportunitySourceType.OFFICIAL, source_name="Source fictive", url=f"https://example.test/{opportunity.pk}", is_primary=True, verified=True)
        if published:
            publish_opportunity_revision(opportunity=opportunity, revision=revision, actor=self.curator)
        return opportunity

    def test_public_list_and_detail_expose_only_published_opportunities(self):
        response = self.client.get(reverse("opportunities:list"))
        self.assertContains(response, "Opportunity publique")
        self.assertNotContains(response, "Opportunity brouillon")
        self.assertEqual(self.client.get(reverse("opportunities:detail", kwargs={"pk": self.published.pk})).status_code, 200)
        self.assertEqual(self.client.get(reverse("opportunities:detail", kwargs={"pk": self.draft.pk})).status_code, 404)

    def test_filters_are_queryset_backed(self):
        response = self.client.get(reverse("opportunities:list"), {"q": "publique", "kind": OpportunityKind.JOB, "remote": "yes"})
        self.assertContains(response, "Opportunity publique")
        response = self.client.get(reverse("opportunities:list"), {"q": "introuvable"})
        self.assertNotContains(response, "Opportunity publique")

    def test_authenticated_user_can_save_and_unsave(self):
        self.client.force_login(self.user)
        url = reverse("opportunities:save-toggle", kwargs={"pk": self.published.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(OpportunitySave.objects.filter(profile=self.user, opportunity=self.published).exists())
        self.client.post(url)
        self.assertFalse(OpportunitySave.objects.filter(profile=self.user, opportunity=self.published).exists())

    def test_save_mutation_requires_post_and_authentication(self):
        url = reverse("opportunities:save-toggle", kwargs={"pk": self.published.pk})
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(url).status_code, 405)

    def test_submission_is_owned_and_does_not_publish_anything(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("opportunities:submit"), {"url": "https://example.test/missing", "title": "Lien manquant", "comment": "Merci de vérifier"})
        self.assertEqual(response.status_code, 302)
        submission = OpportunitySubmission.objects.get(submitted_by=self.user)
        self.assertEqual(submission.status, "pending")
        self.assertEqual(self.client.get(reverse("opportunities:submission-detail", kwargs={"pk": submission.pk})).status_code, 200)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse("opportunities:submission-detail", kwargs={"pk": submission.pk})).status_code, 404)
        self.assertFalse(OpportunityPublicationStatus.PUBLISHED == self.draft.publication_status)
