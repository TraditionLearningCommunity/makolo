from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from rest_framework.test import APIClient

from access.models import Access, AccessCredential, AccessStatus
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role, grant_space_role
from activities.models import (
    Activity,
    ActivityStatus,
    ActivityVisibility,
    OccurrencePlace,
    OccurrencePlaceRole,
    OccurrenceStatus,
    OccurrenceTimingKind,
)
from activities.services import create_occurrence
from capacity.models import CapacityPool, CapacityReservation, CapacityReservationStatus
from capacity.selectors import capacity_availability_many
from commerce.models import CommerceOrder, PaymentMode
from geography.models import Place
from journeys.collaboration_models import JourneyBlocker, JourneyBlockerStatus
from journeys.models import Journey, JourneyRequest, JourneyStatus, RequestStatus, WorkflowKind
from objectives.models import DossierAssignment, DossierJourneyDependency, DossierJourneyLink
from objectives.services import (
    create_dossier,
    create_project,
    link_dossier_to_project,
    link_journey,
)
from opportunities.models import OpportunityKind, OpportunityRequirementKind, OpportunitySourceType
from opportunities.services import (
    add_requirement,
    create_opportunity,
    create_opportunity_revision,
    create_opportunity_source,
    publish_opportunity_revision,
)
from organizations.models import TeamMembership, TeamMembershipStatus
from organizations.services import create_organization
from personal_assets.services import create_personal_asset
from payments.models import (
    PaymentObligation,
    PaymentObligationProcessingMode,
    PaymentObligationReason,
    PaymentObligationStatus,
)
from requirements.contracts import RequirementAssessmentState
from services.models import OpportunityPolicy, ServiceKind, ServiceRequirementAssessment
from services.requirement_services import assess_requirement, derive_requirement_consequence
from services.services import create_service_details, create_service_journey


User = get_user_model()


class Z5DetailAPIContractTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="z5-user",
            email="z5-user@example.test",
            password="x",
        )
        self.other = User.objects.create_user(
            username="z5-other",
            email="z5-other@example.test",
            password="x",
        )
        self.buyer = User.objects.create_user(
            username="z5-buyer",
            email="z5-buyer@example.test",
            password="x",
        )
        self.activity = Activity.objects.create(
            title="Activity Z5",
            short_description="Détail utile",
            created_by=self.user,
            owner_profile=self.user,
            status=ActivityStatus.PUBLISHED,
            visibility=ActivityVisibility.PUBLIC,
        )

    def journey(self, *, beneficiary=None, status=JourneyStatus.CONFIRMED, occurrence=None):
        beneficiary = beneficiary or self.user
        return Journey.objects.create(
            initiated_by=beneficiary,
            beneficiary=beneficiary,
            activity=self.activity,
            occurrence=occurrence,
            workflow=WorkflowKind.REGISTRATION,
            status=status,
        )

    def test_journey_detail_is_scoped_and_preserves_waiting_blocked_and_date_only(self):
        occurrence = create_occurrence(
            activity=self.activity,
            start_date=date(2026, 10, 18),
            timing_kind=OccurrenceTimingKind.DATE_ONLY,
            timezone="Africa/Lubumbashi",
            status=OccurrenceStatus.SCHEDULED,
        )
        waiting = self.journey(
            status=JourneyStatus.PENDING_APPROVAL,
            occurrence=occurrence,
        )
        JourneyRequest.objects.create(
            journey=waiting,
            requester=self.user,
            status=RequestStatus.PENDING,
        )

        self.client.force_authenticate(self.user)
        response = self.client.get(f"/api/v1/me/journeys/{waiting.pk}/")
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(response.json()["meta"]["projection"], "personal.journey.detail")
        self.assertEqual(data["readiness"]["state"], "waiting")
        self.assertTrue(data["readiness"]["waiting"])
        self.assertEqual(data["occurrence"]["timing"]["start_date"], "2026-10-18")
        self.assertIsNone(data["occurrence"]["timing"]["start_time"])
        self.assertIsNone(data["occurrence"]["timing"]["start_at"])

        blocked = self.journey()
        JourneyBlocker.objects.create(
            journey=blocked,
            title="Blocage réel",
            status=JourneyBlockerStatus.ACTIVE,
        )
        blocked_response = self.client.get(f"/api/v1/me/journeys/{blocked.pk}/")
        self.assertEqual(blocked_response.status_code, 200)
        self.assertEqual(blocked_response.json()["data"]["readiness"]["state"], "blocked")
        self.assertTrue(blocked_response.json()["data"]["readiness"]["blockers"])

        self.client.force_authenticate(self.other)
        outsider = self.client.get(f"/api/v1/me/journeys/{waiting.pk}/")
        self.assertEqual(outsider.status_code, 404)


    def test_payment_readiness_is_owner_derived_for_pending_and_satisfied_obligations(self):
        pending = self.journey(status=JourneyStatus.PENDING_PAYMENT)
        PaymentObligation.objects.create(
            journey=pending,
            reason=PaymentObligationReason.OTHER,
            label="Frais Z5",
            amount=Decimal("15.00"),
            currency="USD",
            processing_mode=PaymentObligationProcessingMode.MAKOLO_PROVIDER,
            status=PaymentObligationStatus.PENDING,
            payer_profile=self.user,
            payee_platform=True,
        )

        satisfied = self.journey()
        PaymentObligation.objects.create(
            journey=satisfied,
            reason=PaymentObligationReason.OTHER,
            label="Frais réglés Z5",
            amount=Decimal("15.00"),
            currency="USD",
            processing_mode=PaymentObligationProcessingMode.MAKOLO_PROVIDER,
            status=PaymentObligationStatus.SATISFIED,
            payer_profile=self.user,
            payee_platform=True,
            satisfied_at=timezone.now(),
        )

        self.client.force_authenticate(self.user)
        pending_response = self.client.get(f"/api/v1/me/journeys/{pending.pk}/")
        self.assertEqual(pending_response.status_code, 200)
        pending_data = pending_response.json()["data"]
        pending_readiness = pending_data["readiness"]
        self.assertEqual(pending_readiness["state"], "action_required")
        self.assertTrue(
            any(row["reason"] == "payment_required" for row in pending_readiness["actor_interventions"])
        )
        self.assertEqual(
            pending_data["payment"]["obligations"][0]["state"],
            "pending",
        )
        self.assertEqual(
            pending_data["payment"]["obligations"][0]["amount"],
            "15.00",
        )

        satisfied_response = self.client.get(f"/api/v1/me/journeys/{satisfied.pk}/")
        self.assertEqual(satisfied_response.status_code, 200)
        satisfied_data = satisfied_response.json()["data"]
        satisfied_readiness = satisfied_data["readiness"]
        self.assertEqual(satisfied_readiness["state"], "ready")
        self.assertFalse(
            any(row["reason"] == "payment_required" for row in satisfied_readiness["actor_interventions"])
        )
        self.assertEqual(
            satisfied_data["payment"]["obligations"][0]["state"],
            "satisfied",
        )

    def test_activity_personal_relation_reuses_existing_journey_and_access(self):
        journey = self.journey(status=JourneyStatus.CONFIRMED)
        self.client.force_authenticate(self.user)
        journey_relation = self.client.get(f"/api/v1/activities/{self.activity.pk}/")
        self.assertEqual(journey_relation.status_code, 200)
        self.assertIsNotNone(journey_relation.json()["data"]["personal_relation"])
        self.assertNotEqual(
            journey_relation.json()["data"]["personal_relation"]["state"],
            "none",
        )

        Access.objects.create(
            beneficiary=self.user,
            activity=self.activity,
            journey=journey,
            status=AccessStatus.VALID,
        )
        access_relation = self.client.get(f"/api/v1/activities/{self.activity.pk}/")
        self.assertEqual(access_relation.status_code, 200)
        self.assertEqual(
            access_relation.json()["data"]["personal_relation"]["state"],
            "access_valid",
        )

    def test_occurrence_live_link_requires_actual_participant_projection(self):
        occurrence = create_occurrence(
            activity=self.activity,
            start_at=timezone.now() + timedelta(hours=2),
            end_at=timezone.now() + timedelta(hours=4),
            timezone="Africa/Lubumbashi",
            status=OccurrenceStatus.SCHEDULED,
        )
        self.journey(occurrence=occurrence)

        self.client.force_authenticate(self.user)
        response = self.client.get(f"/api/v1/occurrences/{occurrence.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("live", response.json()["data"]["links"])
        self.assertIn("open_live", response.json()["data"]["capabilities"])

        self.client.force_authenticate(self.other)
        outsider = self.client.get(f"/api/v1/occurrences/{occurrence.pk}/")
        self.assertEqual(outsider.status_code, 200)
        self.assertNotIn("live", outsider.json()["data"]["links"])
        self.assertNotIn("open_live", outsider.json()["data"]["capabilities"])

    def test_capacity_unlimited_and_access_terminal_states_are_preserved(self):
        unlimited = CapacityPool.objects.create(
            activity=self.activity,
            total_quantity=None,
            label="Sans limite",
        )
        self.client.force_authenticate(self.user)
        activity_response = self.client.get(f"/api/v1/activities/{self.activity.pk}/")
        pool = next(
            row for row in activity_response.json()["data"]["capacity"]
            if row["id"] == str(unlimited.pk)
        )
        self.assertTrue(pool["unlimited"])
        self.assertIsNone(pool["available"])
        self.assertFalse(pool["sold_out"])

        second_pool = CapacityPool.objects.create(
            activity=self.activity,
            total_quantity=5,
            label="Batch",
        )
        with self.assertNumQueries(1):
            snapshots = capacity_availability_many(
                [unlimited, second_pool],
                now=timezone.now(),
            )
        self.assertIsNone(snapshots[unlimited.pk].available)
        self.assertEqual(snapshots[second_pool.pk].available, 5)

        revoked = Access.objects.create(
            beneficiary=self.user,
            activity=self.activity,
            status=AccessStatus.REVOKED,
        )
        expired = Access.objects.create(
            beneficiary=self.user,
            activity=self.activity,
            status=AccessStatus.EXPIRED,
        )
        revoked_response = self.client.get(f"/api/v1/me/accesses/{revoked.pk}/")
        expired_response = self.client.get(f"/api/v1/me/accesses/{expired.pk}/")
        self.assertEqual(revoked_response.json()["data"]["right"]["state"], "revoked")
        self.assertEqual(expired_response.json()["data"]["right"]["state"], "expired")

    def test_completed_journey_remains_readable_and_access_projection_has_no_credential(self):
        completed = self.journey(status=JourneyStatus.FULFILLED)
        access = Access.objects.create(
            beneficiary=self.user,
            activity=self.activity,
            journey=completed,
            status=AccessStatus.VALID,
        )
        credential = AccessCredential.objects.create(access=access)

        self.client.force_authenticate(self.user)
        journey_response = self.client.get(f"/api/v1/me/journeys/{completed.pk}/")
        self.assertEqual(journey_response.status_code, 200)

        response = self.client.get(f"/api/v1/me/accesses/{access.pk}/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        rendered = str(payload)
        self.assertEqual(payload["data"]["holder"]["relationship"], "beneficiary")
        self.assertNotIn(str(credential.public_id), rendered)
        self.assertNotIn("credential", rendered.lower())
        self.assertNotIn("qr", rendered.lower())

    def test_buyer_has_bounded_access_visibility_without_becoming_beneficiary(self):
        journey = self.journey(beneficiary=self.other)
        CommerceOrder.objects.create(
            journey=journey,
            buyer=self.buyer,
            payment_mode=PaymentMode.NONE,
            currency="USD",
            subtotal=0,
            discount_total=0,
            total=0,
        )
        access = Access.objects.create(
            beneficiary=self.other,
            activity=self.activity,
            journey=journey,
            status=AccessStatus.VALID,
        )

        self.client.force_authenticate(self.buyer)
        response = self.client.get(f"/api/v1/me/accesses/{access.pk}/")
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["holder"]["relationship"], "purchased_for_other")
        self.assertEqual(data["right"]["state"], "valid")
        self.assertIsNone(data["journey"])
        self.assertNotIn(self.other.email, str(response.json()))

        outsider = User.objects.create_user(
            username="z5-outsider",
            email="z5-outsider@example.test",
            password="x",
        )
        self.client.force_authenticate(outsider)
        self.assertEqual(
            self.client.get(f"/api/v1/me/accesses/{access.pk}/").status_code,
            404,
        )

    def test_public_activity_occurrence_and_capacity_are_owner_domain_details(self):
        occurrence = create_occurrence(
            activity=self.activity,
            start_date=date(2026, 11, 4),
            timing_kind=OccurrenceTimingKind.DATE_ONLY,
            timezone="Africa/Lubumbashi",
            status=OccurrenceStatus.SCHEDULED,
        )
        place = Place.objects.create(
            name="Maison Z5",
            locality="Lubumbashi",
            country_code="CD",
            timezone="Africa/Lubumbashi",
            created_by=self.user,
        )
        OccurrencePlace.objects.create(
            occurrence=occurrence,
            place=place,
            role=OccurrencePlaceRole.PRIMARY,
        )
        pool = CapacityPool.objects.create(
            activity=self.activity,
            occurrence=occurrence,
            total_quantity=2,
            label="Places",
        )
        journey = self.journey(occurrence=occurrence)
        CapacityReservation.objects.create(
            pool=pool,
            journey=journey,
            quantity=2,
            status=CapacityReservationStatus.HELD,
        )

        self.client.force_authenticate(user=None)
        activity_response = self.client.get(f"/api/v1/activities/{self.activity.pk}/")
        self.assertEqual(activity_response.status_code, 200)
        self.assertEqual(activity_response.json()["meta"]["projection"], "activity.detail")

        occurrence_response = self.client.get(f"/api/v1/occurrences/{occurrence.pk}/")
        self.assertEqual(occurrence_response.status_code, 200)
        data = occurrence_response.json()["data"]
        self.assertEqual(data["timing"]["start_date"], "2026-11-04")
        self.assertIsNone(data["timing"]["start_at"])
        self.assertEqual(data["place"]["name"], "Maison Z5")
        self.assertEqual(data["place"]["locality"], "Lubumbashi")
        self.assertEqual(data["capacity"][0]["available"], 0)
        self.assertTrue(data["capacity"][0]["sold_out"])
        self.assertNotIn("held", data["capacity"][0])
        self.assertNotIn("committed", data["capacity"][0])
        self.assertNotIn("live", data["links"])
        self.assertNotIn("queue", data)
        self.assertNotIn("placement", data)
        self.assertNotIn("checkpoint", data)

    def test_private_activity_and_occurrence_do_not_leak_by_uuid(self):
        private = Activity.objects.create(
            title="Privée Z5",
            created_by=self.user,
            owner_profile=self.user,
            status=ActivityStatus.PUBLISHED,
            visibility=ActivityVisibility.PRIVATE,
        )
        occurrence = create_occurrence(
            activity=private,
            start_date=date(2026, 12, 1),
            timing_kind=OccurrenceTimingKind.DATE_ONLY,
            timezone="Africa/Lubumbashi",
            status=OccurrenceStatus.SCHEDULED,
        )

        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(f"/api/v1/activities/{private.pk}/").status_code, 404)
        self.assertEqual(self.client.get(f"/api/v1/occurrences/{occurrence.pk}/").status_code, 404)

        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.get(f"/api/v1/activities/{private.pk}/").status_code, 200)
        self.assertEqual(self.client.get(f"/api/v1/occurrences/{occurrence.pk}/").status_code, 200)

    def test_public_detail_hides_draft_occurrence_and_its_capacity_from_regular_viewer(self):
        draft = create_occurrence(
            activity=self.activity,
            start_date=date(2026, 12, 8),
            timing_kind=OccurrenceTimingKind.DATE_ONLY,
            timezone="Africa/Lubumbashi",
            status=OccurrenceStatus.DRAFT,
        )
        pool = CapacityPool.objects.create(
            activity=self.activity,
            occurrence=draft,
            total_quantity=3,
            label="Draft capacity",
        )

        self.client.force_authenticate(self.other)
        response = self.client.get(f"/api/v1/activities/{self.activity.pk}/")
        self.assertEqual(response.status_code, 200)
        rendered = str(response.json())
        self.assertNotIn(str(draft.pk), rendered)
        self.assertNotIn(str(pool.pk), rendered)
        self.assertEqual(
            self.client.get(f"/api/v1/occurrences/{draft.pk}/").status_code,
            404,
        )

        self.client.force_authenticate(self.user)
        owner_response = self.client.get(f"/api/v1/activities/{self.activity.pk}/")
        self.assertEqual(owner_response.status_code, 200)
        self.assertIn(str(draft.pk), str(owner_response.json()))
        self.assertIn(str(pool.pk), str(owner_response.json()))
        self.assertEqual(
            self.client.get(f"/api/v1/occurrences/{draft.pk}/").status_code,
            200,
        )

    def test_private_engaged_participant_can_open_own_occurrence_but_not_another_one(self):
        private = Activity.objects.create(
            title="Private engaged Z5",
            created_by=self.other,
            owner_profile=self.other,
            status=ActivityStatus.PUBLISHED,
            visibility=ActivityVisibility.PRIVATE,
        )
        own_occurrence = create_occurrence(
            activity=private,
            start_date=date(2026, 12, 10),
            timing_kind=OccurrenceTimingKind.DATE_ONLY,
            timezone="Africa/Lubumbashi",
            status=OccurrenceStatus.SCHEDULED,
        )
        other_occurrence = create_occurrence(
            activity=private,
            start_date=date(2026, 12, 11),
            timing_kind=OccurrenceTimingKind.DATE_ONLY,
            timezone="Africa/Lubumbashi",
            status=OccurrenceStatus.SCHEDULED,
        )
        draft_occurrence = create_occurrence(
            activity=private,
            start_date=date(2026, 12, 12),
            timing_kind=OccurrenceTimingKind.DATE_ONLY,
            timezone="Africa/Lubumbashi",
            status=OccurrenceStatus.DRAFT,
        )
        Journey.objects.create(
            initiated_by=self.user,
            beneficiary=self.user,
            activity=private,
            occurrence=own_occurrence,
            workflow=WorkflowKind.REGISTRATION,
            status=JourneyStatus.CONFIRMED,
        )

        self.client.force_authenticate(self.user)
        self.assertEqual(
            self.client.get(f"/api/v1/activities/{private.pk}/").status_code,
            200,
        )
        self.assertEqual(
            self.client.get(f"/api/v1/occurrences/{own_occurrence.pk}/").status_code,
            200,
        )
        self.assertEqual(
            self.client.get(f"/api/v1/occurrences/{other_occurrence.pk}/").status_code,
            404,
        )
        self.assertEqual(
            self.client.get(f"/api/v1/occurrences/{draft_occurrence.pk}/").status_code,
            404,
        )

    def test_unlisted_activity_is_directly_openable_without_entering_public_discovery_contract(self):
        unlisted = Activity.objects.create(
            title="Unlisted Z5",
            created_by=self.user,
            owner_profile=self.user,
            status=ActivityStatus.PUBLISHED,
            visibility=ActivityVisibility.UNLISTED,
        )
        self.client.force_authenticate(user=None)
        response = self.client.get(f"/api/v1/activities/{unlisted.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["meta"]["scope"], "public")
        self.assertEqual(response.json()["data"]["state"]["visibility"], "unlisted")

    def test_team_membership_alone_does_not_open_private_activity_but_activity_mandate_does(self):
        space = create_organization(creator=self.user, name="Z5 Authority Space")
        private = Activity.objects.create(
            title="Mandated private activity",
            created_by=self.user,
            space=space,
            status=ActivityStatus.PUBLISHED,
            visibility=ActivityVisibility.PRIVATE,
        )
        TeamMembership.objects.create(
            team=space.primary_team,
            user=self.other,
            status=TeamMembershipStatus.ACTIVE,
            invited_by=self.user,
            joined_at=timezone.now(),
        )

        self.client.force_authenticate(self.other)
        self.assertEqual(
            self.client.get(f"/api/v1/activities/{private.pk}/").status_code,
            404,
        )

        grant_activity_role(
            profile=self.other,
            activity=private,
            role=SystemRoleCode.ACTIVITY_LOCAL_MANAGER,
            granted_by=self.user,
            source="z5-test",
        )
        self.assertEqual(
            self.client.get(f"/api/v1/activities/{private.pk}/").status_code,
            200,
        )

    def test_cancelled_and_completed_occurrence_states_are_not_presented_as_future(self):
        cancelled = create_occurrence(
            activity=self.activity,
            start_date=date(2026, 12, 15),
            timing_kind=OccurrenceTimingKind.DATE_ONLY,
            timezone="Africa/Lubumbashi",
            status=OccurrenceStatus.CANCELLED,
        )
        completed = create_occurrence(
            activity=self.activity,
            start_date=date(2026, 1, 15),
            timing_kind=OccurrenceTimingKind.DATE_ONLY,
            timezone="Africa/Lubumbashi",
            status=OccurrenceStatus.COMPLETED,
        )
        self.client.force_authenticate(user=None)

        cancelled_payload = self.client.get(
            f"/api/v1/occurrences/{cancelled.pk}/"
        ).json()["data"]
        completed_payload = self.client.get(
            f"/api/v1/occurrences/{completed.pk}/"
        ).json()["data"]
        self.assertEqual(cancelled_payload["state"]["code"], "cancelled")
        self.assertEqual(cancelled_payload["availability"]["state"], "cancelled")
        self.assertEqual(completed_payload["state"]["code"], "completed")
        self.assertEqual(completed_payload["availability"]["state"], "completed")
        self.assertNotIn("future", str(completed_payload).lower())

    def test_dossier_hidden_dependency_stays_opaque_and_assignment_grants_no_authority(self):
        dossier = create_dossier(
            actor=self.user,
            owner_profile=self.user,
            title="Dossier Z5",
        )
        visible = self.journey()
        hidden_activity = Activity.objects.create(
            title="SECRET HIDDEN JOURNEY",
            created_by=self.other,
            owner_profile=self.other,
            status=ActivityStatus.PUBLISHED,
            visibility=ActivityVisibility.PRIVATE,
        )
        hidden = Journey.objects.create(
            initiated_by=self.other,
            beneficiary=self.other,
            activity=hidden_activity,
            workflow=WorkflowKind.REGISTRATION,
            status=JourneyStatus.DRAFT,
        )
        visible_link = link_journey(actor=self.user, dossier=dossier, journey=visible)
        hidden_link = DossierJourneyLink.objects.create(
            dossier=dossier,
            journey=hidden,
            linked_by=self.other,
        )
        DossierJourneyDependency.objects.create(
            dossier=dossier,
            dependent_link=visible_link,
            required_link=hidden_link,
            created_by=self.other,
        )

        self.client.force_authenticate(self.user)
        response = self.client.get(f"/api/v1/objectives/dossiers/{dossier.pk}/")
        self.assertEqual(response.status_code, 200)
        rendered = str(response.json())
        self.assertNotIn(str(hidden.pk), rendered)
        self.assertNotIn("SECRET HIDDEN JOURNEY", rendered)
        self.assertTrue(response.json()["data"]["readiness"]["partial"])

        # Exercise the invariant directly: a responsibility record must not
        # widen authority. The public assign_dossier service intentionally
        # requires pre-existing management authority and therefore cannot
        # create this legacy/edge state.
        DossierAssignment.objects.create(
            dossier=dossier,
            assignee=self.other,
            assigned_by=self.user,
        )
        self.client.force_authenticate(self.other)
        self.assertEqual(
            self.client.get(f"/api/v1/objectives/dossiers/{dossier.pk}/").status_code,
            404,
        )

    def test_space_membership_does_not_grant_objective_visibility_but_space_mandate_does(self):
        space = create_organization(creator=self.user, name="Z5 Objectives Space")
        dossier = create_dossier(
            actor=self.user,
            owning_space=space,
            title="Space dossier",
        )
        project = create_project(
            actor=self.user,
            owning_space=space,
            title="Space project",
        )
        TeamMembership.objects.create(
            team=space.primary_team,
            user=self.other,
            status=TeamMembershipStatus.ACTIVE,
            invited_by=self.user,
            joined_at=timezone.now(),
        )

        self.client.force_authenticate(self.other)
        self.assertEqual(
            self.client.get(f"/api/v1/objectives/dossiers/{dossier.pk}/").status_code,
            404,
        )
        self.assertEqual(
            self.client.get(f"/api/v1/objectives/projects/{project.pk}/").status_code,
            404,
        )

        grant_space_role(
            profile=self.other,
            space=space,
            role=SystemRoleCode.SPACE_ADMIN,
            granted_by=self.user,
            source="z5-test",
        )
        self.assertEqual(
            self.client.get(f"/api/v1/objectives/dossiers/{dossier.pk}/").status_code,
            200,
        )
        self.assertEqual(
            self.client.get(f"/api/v1/objectives/projects/{project.pk}/").status_code,
            200,
        )

    def test_project_is_horizon_not_task_manager(self):
        dossier = create_dossier(
            actor=self.user,
            owner_profile=self.user,
            title="Objectif composé",
        )
        project = create_project(
            actor=self.user,
            owner_profile=self.user,
            title="Horizon durable",
            starts_on=date(2026, 1, 1),
            ends_on=date(2027, 1, 1),
        )
        link_dossier_to_project(actor=self.user, project=project, dossier=dossier)

        self.client.force_authenticate(self.user)
        response = self.client.get(f"/api/v1/objectives/projects/{project.pk}/")
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["horizon"]["starts_on"], "2026-01-01")
        self.assertEqual(data["visible_dossiers"][0]["id"], str(dossier.pk))
        rendered = str(data).lower()
        self.assertNotIn("tasks", rendered)
        self.assertNotIn("kanban", rendered)
        self.assertNotIn("percentage", rendered)

        self.client.force_authenticate(self.other)
        self.assertEqual(
            self.client.get(f"/api/v1/objectives/projects/{project.pk}/").status_code,
            404,
        )

    def test_personal_asset_existence_does_not_satisfy_service_requirement(self):
        curator = User.objects.create_user(
            username="z5-curator",
            email="z5-curator@example.test",
            password="x",
            is_staff=True,
            is_superuser=True,
        )
        service_activity = Activity.objects.create(
            title="Service Z5",
            created_by=curator,
            owner_profile=curator,
            status=ActivityStatus.PUBLISHED,
        )
        service = create_service_details(
            activity=service_activity,
            actor=curator,
            service_kind=ServiceKind.APPLICATION_SUPPORT,
            opportunity_policy=OpportunityPolicy.REQUIRED,
        )
        opportunity = create_opportunity(actor=curator, kind=OpportunityKind.JOB)
        revision = create_opportunity_revision(
            opportunity=opportunity,
            actor=curator,
            title="Opportunity Z5",
            issuer_name="Issuer",
            timezone_name="Africa/Lubumbashi",
        )
        create_opportunity_source(
            opportunity=opportunity,
            actor=curator,
            source_type=OpportunitySourceType.OFFICIAL,
            source_name="Official",
            url="https://example.test/z5",
            is_primary=True,
            verified=True,
        )
        add_requirement(
            revision=revision,
            actor=curator,
            kind=OpportunityRequirementKind.DOCUMENT,
            title="CV requis",
            position=10,
        )
        publish_opportunity_revision(
            opportunity=opportunity,
            revision=revision,
            actor=curator,
        )
        journey = create_service_journey(
            service=service,
            initiated_by=self.user,
            beneficiary=self.user,
            opportunity=opportunity,
        )
        assessment = journey.service_context.requirement_assessments.get()

        create_personal_asset(
            controller=self.user,
            subject_profile=self.user,
            title="CV déjà dans ma bibliothèque",
        )

        self.client.force_authenticate(self.user)
        response = self.client.get(
            f"/api/v1/me/journeys/{journey.pk}/requirements/{assessment.pk}/"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["assessment"]["state"], "unassessed")
        self.assertNotEqual(data["assessment"]["state"], "satisfied")
        self.assertNotIn("note", data["assessment"])
        self.assertNotIn("evidence", str(data).lower())

        self.client.force_authenticate(self.other)
        self.assertEqual(
            self.client.get(
                f"/api/v1/me/journeys/{journey.pk}/requirements/{assessment.pk}/"
            ).status_code,
            404,
        )

        assess_requirement(
            assessment=assessment,
            actor=curator,
            status=RequirementAssessmentState.SATISFIED,
        )
        self.client.force_authenticate(self.user)
        satisfied = self.client.get(
            f"/api/v1/me/journeys/{journey.pk}/requirements/{assessment.pk}/"
        )
        self.assertEqual(satisfied.status_code, 200)
        self.assertEqual(
            satisfied.json()["data"]["assessment"]["state"],
            "satisfied",
        )
        self.assertIsNone(
            satisfied.json()["data"]["assessment"]["consequence"],
        )

        assessment.refresh_from_db()
        assess_requirement(
            assessment=assessment,
            actor=curator,
            status=RequirementAssessmentState.UNSATISFIED,
        )
        unsatisfied = self.client.get(
            f"/api/v1/me/journeys/{journey.pk}/requirements/{assessment.pk}/"
        )
        self.assertEqual(unsatisfied.status_code, 200)
        self.assertEqual(
            unsatisfied.json()["data"]["assessment"]["state"],
            "unsatisfied",
        )

        assessment.refresh_from_db()
        assessment.status = RequirementAssessmentState.PENDING
        assessment._allow_assessment_transition = True
        assessment.save(update_fields=["status", "updated_at"])
        loaded = (
            ServiceRequirementAssessment.objects.select_related("requirement")
            .prefetch_related(
                "payment_obligation_links__obligation",
                "step_links__journey_step",
                "evidence",
            )
            .get(pk=assessment.pk)
        )
        with self.assertNumQueries(0):
            derive_requirement_consequence(loaded)
