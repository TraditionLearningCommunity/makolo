"""L5: owner-backed depths and independent permission checks."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from activities.models import Activity, Occurrence
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role, revoke_mandate
from capacity.models import CapacityPool
from operations.models import OccurrenceQueue
from operations.occurrence_web_depth import depth_page


User = get_user_model()


class ExperienceDepthsL5Tests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="depth-owner", email="depth-owner@example.test",
        )
        self.finance = User.objects.create_user(
            username="depth-finance", email="depth-finance@example.test",
        )
        self.operator = User.objects.create_user(
            username="depth-operator", email="depth-operator@example.test",
        )
        self.scanner = User.objects.create_user(
            username="depth-scanner", email="depth-scanner@example.test",
        )
        self.outsider = User.objects.create_user(
            username="depth-outsider", email="depth-outsider@example.test",
        )
        self.activity = Activity.objects.create(
            owner_profile=self.owner,
            created_by=self.owner,
            title="Opération avec responsabilités cumulables",
        )
        self.occurrence = Occurrence.objects.create(
            activity=self.activity,
            start_at=timezone.now() - timedelta(minutes=5),
            end_at=timezone.now() + timedelta(hours=2),
        )
        self.finance_mandate = grant_activity_role(
            profile=self.finance, activity=self.activity,
            role=SystemRoleCode.ACTIVITY_FINANCE, granted_by=self.owner,
        )
        self.operator_mandate = grant_activity_role(
            profile=self.operator, activity=self.activity,
            role=SystemRoleCode.ACTIVITY_OPERATIONS_MANAGER, granted_by=self.owner,
        )
        grant_activity_role(
            profile=self.scanner, activity=self.activity,
            role=SystemRoleCode.ACTIVITY_SCANNER, granted_by=self.owner,
        )
        self.queue = OccurrenceQueue.objects.create(
            occurrence=self.occurrence, key="accueil",
            label="Accueil",
        )
        CapacityPool.objects.create(
            activity=self.activity, occurrence=self.occurrence,
            label="Salle", total_quantity=12,
        )
        self.base = (
            f"/api/v1/operations/occurrences/{self.occurrence.pk}/experience"
        )

    def _day(self, user):
        self.client.force_login(user)
        return self.client.get(f"{self.base}/day-of/")

    def test_finance_is_visible_without_operations_permission(self):
        response = self._day(self.finance)
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertIn("finance_view", data["capabilities"])
        self.assertFalse(data["presentation"]["role_switch_required"])
        self.assertNotIn("organizer", data["sections"])
        depths = {row["kind"] for row in data["depths"]}
        self.assertIn("finance", depths)
        self.assertNotIn("operator_queue", depths)
        self.assertNotIn("scanner", depths)
        summary = self.client.get(f"{self.base}/insights/finance/")
        self.assertEqual(summary.status_code, 200)
        self.assertNotIn("payer_email", summary.content.decode())
        self.assertEqual(
            self.client.get(f"{self.base}/insights/capacity/").status_code,
            404,
        )

    def test_operations_owner_sees_real_queue_depth_but_scanner_does_not(self):
        response = self._day(self.operator)
        self.assertEqual(response.status_code, 200)
        depths = {
            row["kind"]: row for row in response.json()["data"]["depths"]
        }
        self.assertIn("operator_queue", depths)
        self.assertTrue(depths["operator_queue"]["can_manage"])
        queue = self.client.get(f"/api/v1/operations/occurrences/{self.occurrence.pk}/queues/")
        self.assertEqual(queue.status_code, 200)
        self.assertEqual(len(queue.json()), 1)
        self.assertEqual(str(queue.json()[0]["id"]), str(self.queue.pk))

        scanner = self._day(self.scanner)
        self.assertEqual(scanner.status_code, 200)
        kinds = {row["kind"] for row in scanner.json()["data"]["depths"]}
        self.assertIn("scanner", kinds)
        self.assertNotIn("operator_queue", kinds)
        self.assertEqual(
            self.client.get(f"/api/v1/operations/occurrences/{self.occurrence.pk}/queues/").status_code,
            404,
        )

    def test_outsider_and_revoked_financier_cannot_view_insights(self):
        self.assertEqual(self._day(self.outsider).status_code, 404)
        self.assertEqual(
            self.client.get(f"{self.base}/insights/finance/").status_code,
            404,
        )
        self.assertEqual(self._day(self.finance).status_code, 200)
        revoke_mandate(mandate=self.finance_mandate, actor=self.owner)
        self.assertEqual(
            self.client.get(f"{self.base}/insights/finance/").status_code,
            404,
        )
        self.assertEqual(self.client.get(f"{self.base}/day-of/").status_code, 404)

    def test_personal_readiness_depth_keeps_grouped_checks(self):
        projection = {
            "depths": [{
                "kind": "readiness", "label": "Ma préparation",
                "territory": "participant",
            }],
            "sections": {
                "participant": {
                    "readiness": {
                        "state": "blocked",
                        "blockers": [{
                            "key": "operations.access.me",
                            "summary": "Accès indisponible",
                            "reason": "participant_access_unavailable",
                            "source": "access.access",
                        }],
                        "waiting": [{
                            "key": "operations.placement.me",
                            "summary": "Placement en attente",
                            "source": "operations.placement",
                        }],
                        "actor_interventions": [],
                        "ready": [],
                    }
                }
            },
        }
        detail = depth_page(
            occurrence=self.occurrence, actor=self.operator,
            projection=projection, kind="readiness",
        )
        self.assertEqual(len(detail["rows"]), 2)
        self.assertEqual(detail["rows"][0]["label"], "Accès indisponible")
        self.assertEqual(detail["rows"][0]["state"], "blocking")
        self.assertEqual(detail["rows"][1]["state"], "waiting")
        self.assertEqual(detail["rows"][1]["source"], "operations.placement")

    def test_dual_role_readiness_stays_on_participant_territory(self):
        projection = {
            "depths": [{
                "kind": "readiness",
                "label": "Ma préparation",
                "territory": "participant",
            }],
            "sections": {
                "participant": {
                    "readiness": {
                        "blockers": [{"key": "my-access", "summary": "Mon accès"}],
                    },
                },
                "organizer": {
                    "operational_readiness": {
                        "contributors": [{
                            "key": "private-operations",
                            "summary": "Préparation de l'organisateur",
                        }],
                    },
                },
            },
        }
        detail = depth_page(
            occurrence=self.occurrence, actor=self.operator,
            projection=projection, kind="readiness",
        )
        self.assertEqual(len(detail["rows"]), 1)
        self.assertEqual(detail["rows"][0]["label"], "Mon accès")

    def test_operator_readiness_keeps_flat_owner_contributors(self):
        contributor = {"key": "operations.queue", "state": "action_required"}
        projection = {
            "depths": [{
                "kind": "readiness", "label": "Préparation",
                "territory": "organizer",
            }],
            "sections": {
                "organizer": {
                    "operational_readiness": {"contributors": [contributor]}
                }
            },
        }
        detail = depth_page(
            occurrence=self.occurrence, actor=self.operator,
            projection=projection, kind="readiness",
        )
        self.assertEqual(detail["rows"], [contributor])

    def test_web_depth_rejects_operator_mutation_without_manage_authority(self):
        url = (
            f"/me/occurrences/{self.occurrence.pk}/depth/operator_queue/"
        )
        self.client.force_login(self.finance)
        response = self.client.post(
            url, {"action": "close", "item_id": str(self.queue.pk)},
        )
        self.assertEqual(response.status_code, 404)
        self.queue.refresh_from_db()
        self.assertEqual(self.queue.status, "open")

    def test_owner_depth_requires_fresh_scope_for_business_action(self):
        url = (
            f"/me/occurrences/{self.occurrence.pk}/depth/operator_queue/"
        )
        self.client.force_login(self.operator)
        page = self.client.get(url)
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Accueil")
        revoke_mandate(mandate=self.operator_mandate, actor=self.owner)
        response = self.client.post(
            url, {"action": "close", "item_id": str(self.queue.pk)},
        )
        self.assertEqual(response.status_code, 404)
        self.queue.refresh_from_db()
        self.assertEqual(self.queue.status, "open")
