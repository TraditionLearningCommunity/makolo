from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from operations.models import OperationsAuditLog
from opportunities.models import Opportunity, OpportunityPublicationStatus
from organizations.models import Organization
from events.models import Event, EventStatus, EventVisibility
from authorization.services import revoke_mandate

from authorization.constants import SystemRoleCode
from authorization.platform_services import grant_platform_role
from core.platform_presentation import platform_modules_for
from recognition.models import RecognitionPolicy


User = get_user_model()


class PlatformWebContractTests(TestCase):
    def setUp(self):
        self.visitor = User.objects.create_user(
            username="platform-none", email="platform-none@test.local", password="x"
        )
        self.staff = User.objects.create_user(
            username="platform-staff", email="platform-staff@test.local", password="x",
            is_staff=True,
        )
        self.operator = User.objects.create_user(
            username="platform-operator", email="platform-operator@test.local", password="x"
        )
        self.curator = User.objects.create_user(
            username="platform-curator", email="platform-curator@test.local", password="x"
        )
        grant_platform_role(
            profile=self.operator, role=SystemRoleCode.PLATFORM_ADMIN,
            granted_by=self.operator,
        )
        grant_platform_role(
            profile=self.curator, role=SystemRoleCode.OPPORTUNITY_CURATOR,
            granted_by=self.curator,
        )

    def test_anonymous_is_redirected_for_web_and_rejected_for_api(self):
        self.assertEqual(self.client.get("/platform/").status_code, 302)
        self.assertIn(self.client.get("/api/v1/platform/capabilities/").status_code, (401, 403))

    def test_staff_flag_is_not_permission(self):
        for actor in (self.staff, self.visitor):
            self.client.force_login(actor)
            self.assertEqual(self.client.get("/platform/").status_code, 403)
            self.assertEqual(self.client.get("/platform/system/").status_code, 403)
            self.assertEqual(self.client.get("/platform/recognition/").status_code, 403)
            self.assertEqual(self.client.get("/api/v1/platform/capabilities/").status_code, 403)

    def test_operator_has_canonical_modules_and_nocache(self):
        self.client.force_login(self.operator)
        response = self.client.get("/platform/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Makolo Platform")
        self.assertIn("no-store", response["Cache-Control"])
        keys = {module["key"] for module in platform_modules_for(self.operator)}
        self.assertIn("operations", keys)
        self.assertIn("interoperability", keys)
        self.assertEqual(
            keys, {item["key"] for item in
                   self.client.get("/api/v1/platform/capabilities/").data["modules"]}
        )

    def test_specialized_curator_has_no_operations_navigation_or_deeplinks(self):
        self.client.force_login(self.curator)
        response = self.client.get("/platform/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Curation")
        self.assertNotContains(response, 'href="/platform/system/"', html=False)
        self.assertContains(response, 'href="/platform/investigate/"', html=False)
        self.assertNotContains(response, 'href="/platform/recognition/"', html=False)
        self.assertEqual(self.client.get("/platform/system/").status_code, 403)
        self.assertEqual(self.client.get("/platform/interoperability/").status_code, 403)
        search = self.client.get("/platform/investigate/?q=secret")
        self.assertEqual(search.status_code, 200)
        self.assertNotContains(search, "Spaces — correspondances", html=False)

    def test_operator_investigation_is_explicitly_bounded(self):
        self.client.force_login(self.operator)
        response = self.client.get("/platform/investigate/?q=not-present")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Recherche owner-fédérée partielle")
        self.assertNotContains(response, "Credentials complets")

    def test_recognition_simulation_is_readonly_and_requires_permission(self):
        policy = RecognitionPolicy.objects.create(
            code="platform-test-policy", version=1, name="Test policy"
        )
        self.client.force_login(self.visitor)
        self.assertEqual(
            self.client.get(reverse("platform_web:recognition-simulation", kwargs={"pk": policy.pk})).status_code,
            403,
        )
        self.client.force_login(self.operator)
        with patch("recognition.simulation.simulate_policy", return_value={
            "signals": 0, "matches": 0, "projected_credits": 0, "objects": 0
        }):
            response = self.client.get(reverse(
                "platform_web:recognition-simulation", kwargs={"pk": policy.pk}
            ))
        self.assertEqual(response.status_code, 200)
        policy.refresh_from_db()
        self.assertEqual(policy.status, "draft")
        self.assertContains(response, "sans écriture ni publication")

    def test_space_decision_requires_reason_confirmation_and_fresh_state(self):
        space = Organization.objects.create(
            name="Platform decision", slug="platform-decision", created_by=self.operator
        )
        path = reverse("platform_web:space-decision", kwargs={"pk": space.pk})
        self.client.force_login(self.operator)
        self.assertEqual(self.client.get(path).status_code, 200)
        before = OperationsAuditLog.objects.count()
        missing = self.client.post(path, {
            "expected_state": "active", "status": "suspended", "reason": "Safety review",
        })
        self.assertEqual(missing.status_code, 400)
        space.refresh_from_db()
        self.assertEqual(space.lifecycle, "active")
        decision = {
            "expected_state": "active", "status": "suspended",
            "reason": "Human review of incident", "confirm": "1",
        }
        self.assertEqual(self.client.post(path, decision).status_code, 302)
        space.refresh_from_db()
        self.assertEqual(space.lifecycle, "suspended")
        logs = OperationsAuditLog.objects.filter(
            action="platform.space_lifecycle_decision", target_id=str(space.pk)
        )
        self.assertEqual(logs.count(), 1)
        self.assertEqual(logs.first().actor, self.operator)
        self.assertEqual(logs.first().metadata["reason"], decision["reason"])
        self.assertEqual(self.client.post(path, decision).status_code, 409)
        self.assertEqual(logs.count(), 1)
        self.assertGreater(OperationsAuditLog.objects.count(), before)

    def test_event_decision_uses_owner_service_and_rejects_stale_submit(self):
        start = timezone.now() + timedelta(days=10)
        event = Event.objects.create(
            organizer=self.operator, title="Event to moderate",
            status=EventStatus.PUBLISHED, visibility=EventVisibility.PUBLIC,
            start_at=start, end_at=start + timedelta(hours=2),
        )
        self.client.force_login(self.operator)
        path = reverse("platform_web:event-decision", kwargs={"pk": event.pk})
        response = self.client.post(path, {
            "action": "unlist", "reason": "Required investigation",
            "expected_state": "published:public", "confirm": "1",
        })
        self.assertEqual(response.status_code, 302)
        event.refresh_from_db()
        self.assertEqual(event.visibility, EventVisibility.UNLISTED)
        self.assertEqual(OperationsAuditLog.objects.filter(
            action="event.moderation.unlist", target_id=str(event.pk)
        ).count(), 1)
        self.assertEqual(self.client.post(path, {
            "action": "unlist", "reason": "Required investigation",
            "expected_state": "published:public", "confirm": "1",
        }).status_code, 409)

    def test_permission_revocation_hides_platform_and_denies_post(self):
        space = Organization.objects.create(
            name="Revoked Platform", slug="revoked-platform", created_by=self.operator
        )
        path = reverse("platform_web:space-decision", kwargs={"pk": space.pk})
        self.client.force_login(self.operator)
        self.assertEqual(self.client.get(path).status_code, 200)
        mandate = self.operator.authority_mandates.filter(
            role__code=SystemRoleCode.PLATFORM_ADMIN
        ).first()
        revoke_mandate(mandate=mandate)
        self.assertEqual(self.client.post(path, {
            "status": "suspended", "reason": "Should not be allowed",
            "expected_state": "active", "confirm": "1",
        }).status_code, 403)
        space.refresh_from_db()
        self.assertEqual(space.lifecycle, "active")

    def test_recognition_publication_requires_confirmation_and_rejects_replay(self):
        policy = RecognitionPolicy.objects.create(
            code="platform-policy-to-publish", version=1, name="Publish preview",
            status="simulated",
        )
        path = reverse("platform_web:recognition-action", kwargs={
            "pk": policy.pk, "action": "publish",
        })
        self.client.force_login(self.operator)
        self.assertEqual(self.client.post(path, {
            "expected_status": "simulated", "reason": "Reviewed policy change",
        }).status_code, 400)
        self.assertEqual(self.client.post(path, {
            "expected_status": "simulated", "reason": "Reviewed policy change",
            "confirm": "1",
        }).status_code, 302)
        policy.refresh_from_db()
        self.assertIn(policy.status, ("active", "scheduled"))
        self.assertEqual(self.client.post(path, {
            "expected_status": "simulated", "reason": "Reviewed policy change",
            "confirm": "1",
        }).status_code, 409)
        audit = OperationsAuditLog.objects.filter(target_id=str(policy.pk), action__startswith="recognition.policy_")
        self.assertEqual(audit.count(), 1)
        self.assertEqual(audit.first().actor, self.operator)

    def test_recognition_simulation_records_owner_audit_without_publishing(self):
        policy = RecognitionPolicy.objects.create(
            code="platform-policy-sim", version=1, name="Simulate preview"
        )
        path = reverse("platform_web:recognition-action", kwargs={
            "pk": policy.pk, "action": "simulate",
        })
        self.client.force_login(self.operator)
        with patch("recognition.governance_services.simulate_policy", return_value={
            "signals": 0, "matches": 0, "projected_credits": 0, "objects": 0
        }):
            self.assertEqual(self.client.post(path, {
                "expected_status": "draft", "reason": "Reviewed last month",
                "confirm": "1",
            }).status_code, 302)
        policy.refresh_from_db()
        self.assertEqual(policy.status, "simulated")
        audit = OperationsAuditLog.objects.get(
            target_id=str(policy.pk), action="recognition.policy_simulated"
        )
        self.assertEqual(audit.metadata["reason"], "Reviewed last month")

    def test_opportunity_merge_requires_permission_reason_and_fresh_owner_revision(self):
        survivor = Opportunity.objects.create(kind="job", created_by=self.operator)
        duplicate = Opportunity.objects.create(kind="job", created_by=self.operator)
        path = reverse("platform_web:opportunity-merge", kwargs={"pk": survivor.pk})
        self.client.force_login(self.visitor)
        self.assertEqual(self.client.get(path).status_code, 403)
        self.client.force_login(self.operator)
        self.assertEqual(self.client.get(path).status_code, 200)
        post = {
            "duplicate": "%s|%s" % (duplicate.pk, duplicate.updated_at.isoformat()),
            "expected_canonical": survivor.updated_at.isoformat(),
            "reason": "Confirmed duplicate of canonical source",
        }
        self.assertEqual(self.client.post(path, post).status_code, 400)
        post["confirm"] = "1"
        self.assertEqual(self.client.post(path, post).status_code, 302)
        duplicate.refresh_from_db()
        self.assertEqual(duplicate.publication_status, OpportunityPublicationStatus.MERGED)
        self.assertEqual(duplicate.merged_into_id, survivor.pk)
        self.assertEqual(self.client.post(path, post).status_code, 409)
        audit = OperationsAuditLog.objects.filter(
            target_id=str(duplicate.pk), action="opportunity.merge_decision"
        )
        self.assertEqual(audit.count(), 1)
        self.assertEqual(audit.first().actor, self.operator)
        self.assertEqual(audit.first().metadata["reason"], post["reason"])
