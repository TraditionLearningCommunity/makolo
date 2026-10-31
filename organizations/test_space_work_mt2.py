"""MT2: stable owner references, contextual handoffs and honest coverage.

These are server contract tests; they do not claim Flutter or Web N2 closure.
"""
from datetime import timedelta
from urllib.parse import parse_qs, urlparse

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from activities.models import Activity, Occurrence, OccurrenceStatus
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role, grant_space_role, revoke_mandate
from journeys.models import (
    Journey, JourneyRequest, JourneyStatus, RequestPurpose, WorkflowKind,
)
from organizations.models import Organization, SpaceArchetype
from services.models import ServiceDetails, ServiceJourneyContext, ServiceKind


class SpaceWorkMT2ContractTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="mt2-owner", password="x",
        )
        self.outsider = User.objects.create_user(
            username="mt2-outsider", password="x",
        )
        self.space = Organization.objects.create(
            name="MT2 Espace", slug="mt2-space", created_by=self.owner,
        )
        grant_space_role(
            profile=self.owner, space=self.space,
            role=SystemRoleCode.SPACE_OWNER, granted_by=self.owner,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.owner)
        self.url = "/api/v1/organizations/workspaces/mt2-space/work/"

    def activity(self, title, *, status="published"):
        return Activity.objects.create(
            title=title, space=self.space, created_by=self.owner,
            status=status,
        )

    @staticmethod
    def row(response, source_kind, pk):
        for section in response.data["sections"].values():
            for item in section["items"]:
                if item["source"] == {"kind": source_kind, "id": str(pk)}:
                    return item
        raise AssertionError(f"Missing authorized {source_kind} row {pk}")

    def test_all_eight_grammars_reuse_identity_and_real_owner_selection(self):
        work = self.activity("Activité durable")
        for archetype in (
            SpaceArchetype.GENERIC,
            SpaceArchetype.COMMUNITY,
            SpaceArchetype.EDUCATION,
            SpaceArchetype.SERVICE_PROVIDER,
            SpaceArchetype.COMMERCE,
            SpaceArchetype.TRANSPORT_OPERATOR,
            SpaceArchetype.CREATIVE,
            SpaceArchetype.MEDIA,
        ):
            with self.subTest(archetype=archetype):
                self.space.archetype = archetype
                self.space.save(update_fields=["archetype", "updated_at"])
                response = self.client.get(self.url)
                self.assertEqual(response.status_code, 200, response.data)
                item = self.row(response, "activity", work.pk)
                self.assertEqual(item["entry_identity"], f"activity:{work.pk}")
                self.assertEqual(item["owner_reference"], item["source"])
                handoffs = item["owner_handoffs"]
                self.assertEqual([h["intent"] for h in handoffs], ["inspect"])
                self.assertEqual(handoffs[0]["owner"], item["source"])
                self.assertEqual(handoffs[0]["channel"], "space_work")
                self.assertEqual(item["links"]["selection"], handoffs[0]["url"])
                selected = self.client.get(handoffs[0]["url"])
                self.assertEqual(selected.status_code, 200, selected.data)
                self.assertEqual(selected.data["selection"]["entry_identity"], item["entry_identity"])
                self.assertEqual(selected.data["composition_state"], "partial")
                self.assertEqual(response.data["composition_state"], "established")
                self.assertEqual(response.data["business_world"]["perspectives"][0]["coverage_state"], "established")

    def test_limited_mandate_keeps_selection_and_coverage_narrow(self):
        allowed = self.activity("Activity de mon mandat")
        hidden = self.activity("Activity hors mandat")
        mandate = grant_activity_role(
            profile=self.owner, activity=allowed,
            role_code=SystemRoleCode.ACTIVITY_MANAGER,
            granted_by=self.owner,
        )
        responsibility = f"mandate:{mandate.pk}"
        response = self.client.get(self.url, {"responsibility": responsibility})
        self.assertEqual(response.status_code, 200, response.data)
        item = self.row(response, "activity", allowed.pk)
        self.assertNotIn(hidden.title, str(response.data))
        self.assertEqual(response.data["composition_state"], "partial")
        self.assertEqual(response.data["coverage_state"], "partial")
        self.assertEqual(response.data["business_world"]["perspectives"][0]["coverage_state"], "partial")
        self.assertTrue(all(
            section["coverage_state"] == "partial"
            for section in response.data["sections"].values()
        ))
        query = parse_qs(urlparse(item["links"]["selection"]).query)
        self.assertEqual(query["responsibility"], [responsibility])
        selected = self.client.get(item["links"]["selection"])
        self.assertEqual(selected.status_code, 200, selected.data)
        self.assertEqual(selected.data["selection"]["owner_reference"]["id"], str(allowed.pk))
        denied = self.client.get(self.url, {
            "responsibility": responsibility,
            "kind": "activity", "id": str(hidden.pk),
        })
        self.assertIsNone(denied.data["selection"])
        self.assertNotIn(hidden.title, str(denied.data))
        revoke_mandate(mandate=mandate, actor=self.owner)
        self.assertEqual(self.client.get(item["links"]["selection"]).status_code, 404)

    def test_request_handoff_exists_only_for_a_real_request_owner(self):
        self.space.archetype = SpaceArchetype.EDUCATION
        self.space.save(update_fields=["archetype", "updated_at"])
        programme = self.activity("Programme")
        learner = User.objects.create_user(
            username="mt2-learner", email="mt2-private@test.local", password="x",
        )
        journey = Journey.objects.create(
            initiated_by=learner, beneficiary=learner, activity=programme,
            workflow=WorkflowKind.REGISTRATION,
            status=JourneyStatus.PENDING_APPROVAL,
        )
        before = self.client.get(self.url)
        entry = self.row(before, "journey", journey.pk)
        self.assertEqual([h["intent"] for h in entry["owner_handoffs"]], ["inspect"])
        self.assertNotIn("request_detail", entry["links"])

        request = JourneyRequest.objects.create(
            journey=journey, requester=learner,
            purpose=RequestPurpose.REGISTRATION,
        )
        response = self.client.get(self.url)
        entry = self.row(response, "journey", journey.pk)
        self.assertEqual(
            [h["intent"] for h in entry["owner_handoffs"]],
            ["inspect", "open_request"],
        )
        request_handoff = entry["owner_handoffs"][1]
        self.assertEqual(request_handoff["owner"], {
            "kind": "journey_request", "id": str(request.pk),
        })
        self.assertEqual(request_handoff["url"], entry["links"]["request_detail"])
        self.assertEqual(self.client.get(request_handoff["url"]).status_code, 200)
        self.assertNotIn(learner.email, str(response.data))
        self.client.force_authenticate(self.outsider)
        self.assertEqual(self.client.get(request_handoff["url"]).status_code, 404)

    def test_real_service_case_has_separate_inspect_and_operator_handoffs(self):
        self.space.archetype = SpaceArchetype.SERVICE_PROVIDER
        self.space.save(update_fields=["archetype", "updated_at"])
        activity = self.activity("Prestation")
        ServiceDetails.objects.create(
            activity=activity,
            service_kind=ServiceKind.ADMINISTRATIVE_SUPPORT,
        )
        beneficiary = User.objects.create_user(
            username="mt2-service-beneficiary", password="x",
        )
        case = Journey.objects.create(
            initiated_by=beneficiary, beneficiary=beneficiary,
            activity=activity, workflow=WorkflowKind.SERVICE,
            status=JourneyStatus.IN_PROGRESS,
        )
        operator = User.objects.create_user(
            username="mt2-service-operator", password="x",
        )
        grant_activity_role(
            profile=operator, activity=activity,
            role_code=SystemRoleCode.ACTIVITY_SERVICE_MANAGER,
            granted_by=self.owner,
        )
        self.client.force_authenticate(operator)
        before = self.client.get(self.url)
        self.assertEqual(
            [h["intent"] for h in self.row(before, "journey", case.pk)["owner_handoffs"]],
            ["inspect"],
        )
        ServiceJourneyContext.objects.create(journey=case)
        response = self.client.get(self.url)
        item = self.row(response, "journey", case.pk)
        self.assertEqual(
            [h["intent"] for h in item["owner_handoffs"]],
            ["inspect", "open_service_case"],
        )
        self.assertEqual(item["owner_handoffs"][1]["channel"], "web")
        self.assertEqual(item["owner_handoffs"][1]["url"], item["links"]["detail"])
        self.assertEqual(response.data["composition_state"], "partial")
        self.assertNotIn(beneficiary.email if beneficiary.email else "private-unknown", str(response.data))

    def test_day_of_is_separate_from_owner_inspection_only_when_authorized(self):
        activity = self.activity("Réalisation")
        occurrence = Occurrence.objects.create(
            activity=activity, label="Session du jour",
            start_at=timezone.now() + timedelta(minutes=10),
            end_at=timezone.now() + timedelta(hours=2),
            status=OccurrenceStatus.SCHEDULED,
        )
        response = self.client.get(self.url)
        item = self.row(response, "occurrence", occurrence.pk)
        self.assertEqual(
            [h["intent"] for h in item["owner_handoffs"]],
            ["inspect", "open_day_of"],
        )
        self.assertEqual(item["owner_handoffs"][1]["url"], item["links"]["day_of"])
        self.client.force_authenticate(self.outsider)
        self.assertEqual(self.client.get(item["owner_handoffs"][0]["url"]).status_code, 404)

    def test_continuation_is_scoped_bounded_and_does_not_claim_full_coverage(self):
        expected = [self.activity(f"Brouillon {index:02}", status="draft") for index in range(22)]
        first = self.client.get(self.url)
        self.assertEqual(first.status_code, 200, first.data)
        section = first.data["sections"]["preparation"]
        self.assertTrue(section["has_more"])
        self.assertEqual(section["coverage_state"], "established")
        continuation = section["links"]["continuation"]
        params = parse_qs(urlparse(continuation).query)
        self.assertEqual(params["section"], ["preparation"])
        self.assertEqual(params["offset"], ["20"])
        self.assertEqual(params["responsibility"], ["all"])
        result = self.client.get(continuation)
        self.assertEqual(result.status_code, 200, result.data)
        self.assertEqual(result.data["composition_state"], "partial")
        self.assertEqual(result.data["sections"]["preparation"]["coverage_state"], "partial")
        rows = section["items"] + result.data["sections"]["preparation"]["items"]
        self.assertEqual(
            [row["source"]["id"] for row in rows],
            [str(activity.pk) for activity in expected],
        )
        self.assertNotIn("continuation", result.data["sections"]["preparation"]["links"])
        self.assertFalse(result.data["sections"]["preparation"]["has_more"])
