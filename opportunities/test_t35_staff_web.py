from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from authorization.constants import SystemRoleCode
from authorization.platform_services import grant_platform_role

from .models import OpportunityKind, OpportunitySourceCheckResult, OpportunitySourceStatus, OpportunitySubmissionStatus
from .services import (
    create_opportunity,
    create_opportunity_revision,
    create_opportunity_source,
    submit_opportunity,
)


User = get_user_model()


class T35OpportunityStaffWebTests(TestCase):
    def setUp(self):
        self.curator = User.objects.create_user(username="t35-curator", email="t35-curator@makolo.test", password="x")
        self.normal = User.objects.create_user(username="t35-normal", email="t35-normal@makolo.test", password="x")
        grant_platform_role(profile=self.curator, role=SystemRoleCode.OPPORTUNITY_CURATOR)

    def _draft(self):
        opportunity = create_opportunity(actor=self.curator, kind=OpportunityKind.JOB)
        revision = create_opportunity_revision(
            opportunity=opportunity,
            actor=self.curator,
            title="Emploi fictif T35",
            issuer_name="Entreprise fictive",
        )
        return opportunity, revision

    def test_curator_dashboard_is_permission_based_not_is_staff(self):
        self.assertFalse(self.curator.is_staff)
        self.client.force_login(self.curator)
        response = self.client.get(reverse("opportunities:staff-dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Curation Makolo")

        self.client.force_login(self.normal)
        self.assertEqual(self.client.get(reverse("opportunities:staff-dashboard")).status_code, 403)

    def test_curator_can_create_draft_and_revision_from_product_surface(self):
        self.client.force_login(self.curator)
        response = self.client.post(reverse("opportunities:staff-create"), {"kind": OpportunityKind.SCHOLARSHIP})
        self.assertEqual(response.status_code, 302)
        detail_url = response.headers["Location"]
        response = self.client.post(
            f"{detail_url}revisions/new/",
            {
                "title": "Bourse fictive T35",
                "issuer_name": "Fondation fictive",
                "summary": "Programme de démonstration",
                "timezone_name": "Africa/Lubumbashi",
                "remote_allowed": "unknown",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Bourse fictive T35")

    def test_curator_can_review_user_submission_without_granting_publication(self):
        submission = submit_opportunity(
            submitted_by=self.normal,
            url="https://example.test/opportunity-t35",
            title="Lien proposé",
            comment="À vérifier",
        )
        self.client.force_login(self.curator)
        response = self.client.post(
            reverse("opportunities:staff-submission-review", args=[submission.pk]),
            {"decision": OpportunitySubmissionStatus.REJECTED, "review_note": "Source non retenue"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        submission.refresh_from_db()
        self.assertEqual(submission.status, OpportunitySubmissionStatus.REJECTED)
        self.assertIsNone(submission.resolved_opportunity_id)

    def test_source_check_updates_append_only_source_state_through_service(self):
        opportunity, _ = self._draft()
        source = create_opportunity_source(
            opportunity=opportunity,
            actor=self.curator,
            source_type="official",
            source_name="Source officielle fictive",
            url="https://example.test/source-t35",
            is_primary=True,
        )
        self.client.force_login(self.curator)
        response = self.client.post(
            reverse("opportunities:staff-source-check", args=[opportunity.pk, source.pk]),
            {"result": OpportunitySourceCheckResult.CHANGED, "note": "Contenu modifié"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        source.refresh_from_db()
        self.assertEqual(source.status, OpportunitySourceStatus.CHANGED)
        self.assertEqual(source.checks.count(), 1)
