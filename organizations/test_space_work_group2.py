"""Group 2: owner-backed Programmes and Prestations, with minimum disclosure."""
from datetime import timedelta

from django.test import Client, TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from activities.models import Activity, Occurrence, OccurrenceStatus
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role, grant_space_role
from journeys.models import (
    Journey, JourneyRequest, JourneyStatus, RequestPurpose,
    WorkflowKind,
)
from opportunities.models import (
    Opportunity, OpportunityKind, OpportunityRequirement,
    OpportunityRequirementKind, OpportunityRevision,
)
from organizations.models import Organization, SpaceArchetype
from requirements.contracts import RequirementAssessmentState
from services.models import (
    OpportunityPolicy, ServiceDetails, ServiceJourneyContext,
    ServiceKind, ServiceRequirementAssessment,
)


class SpaceWorkGroup2Tests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="group2-owner", password="x",
        )
        self.outsider = User.objects.create_user(
            username="group2-outsider", password="x",
        )
        self.space = Organization.objects.create(
            name="Group 2 Space", slug="group-2", created_by=self.owner,
        )
        grant_space_role(
            profile=self.owner, space=self.space,
            role=SystemRoleCode.SPACE_OWNER, granted_by=self.owner,
        )
        self.client = APIClient()
        self.web = Client()
        self.url = "/api/v1/organizations/workspaces/group-2/work/"

    def activity(self, title):
        return Activity.objects.create(
            title=title, space=self.space, created_by=self.owner,
            status="published",
        )

    def beneficiary(self, username):
        return User.objects.create_user(
            username=username, email=username + "@private.test", password="x",
        )

    def test_programme_precedes_real_session_and_registration(self):
        self.space.archetype = SpaceArchetype.EDUCATION
        self.space.save(update_fields=["archetype", "updated_at"])
        programme = self.activity("Programme durable")
        session = Occurrence.objects.create(
            activity=programme, label="Session du mardi",
            start_at=timezone.now() + timedelta(days=3),
            status=OccurrenceStatus.SCHEDULED,
        )
        learner = self.beneficiary("group2-learner")
        registration = Journey.objects.create(
            initiated_by=learner, beneficiary=learner, activity=programme,
            workflow=WorkflowKind.REGISTRATION,
            status=JourneyStatus.PENDING_APPROVAL,
        )
        self.client.force_authenticate(self.owner)
        result = self.client.get(self.url)
        self.assertEqual(result.status_code, 200, result.data)
        self.assertEqual(result.data["presentation"]["section_order"],
                         ["activities", "upcoming", "requests"])
        self.assertEqual(
            [g["identity"] for g in result.data["business_world"]["reading_groups"]],
            ["portfolio", "sessions", "registrations"],
        )
        row = result.data["sections"]["activities"]["items"][0]
        self.assertEqual(row["context"]["next_occurrence"]["id"], str(session.pk))
        self.assertEqual(result.data["presentation"]["next_occurrence_label"],
                         "Prochaine session")
        request = result.data["sections"]["requests"]["items"][0]
        self.assertEqual(request["source"]["id"], str(registration.pk))
        self.assertEqual(request["context"]["work_label"], "Inscription")
        self.assertEqual(request["continuity_facet"]["next"], [])
        self.assertNotIn("open_request", request["capabilities"])
        self.assertNotIn("request_detail", request["links"])
        self.assertNotIn(learner.email, str(result.data))
        selected = self.client.get(request["links"]["selection"])
        self.assertEqual(selected.status_code, 200, selected.data)
        self.assertEqual(
            selected.data["selection"]["source"]["id"], str(registration.pk)
        )
        self.client.force_authenticate(self.outsider)
        self.assertEqual(self.client.get(request["links"]["selection"]).status_code,
                         404)

    def test_registration_decision_handoff_requires_real_request(self):
        self.space.archetype = SpaceArchetype.EDUCATION
        self.space.save(update_fields=["archetype", "updated_at"])
        programme = self.activity("Formation à inscription")
        learner = self.beneficiary("group2-actual-request")
        journey = Journey.objects.create(
            initiated_by=learner, beneficiary=learner, activity=programme,
            workflow=WorkflowKind.REGISTRATION,
            status=JourneyStatus.PENDING_APPROVAL,
        )
        real_request = JourneyRequest.objects.create(
            journey=journey, requester=learner,
            purpose=RequestPurpose.REGISTRATION,
        )
        self.client.force_authenticate(self.owner)
        result = self.client.get(self.url)
        self.assertEqual(result.status_code, 200, result.data)
        row = result.data["sections"]["requests"]["items"][0]
        self.assertIn("open_request", row["capabilities"])
        self.assertIn(str(real_request.pk), row["links"]["request_detail"])
        detail = self.client.get(row["links"]["request_detail"])
        self.assertEqual(detail.status_code, 200, detail.data)
        self.assertEqual(detail.data["request"]["id"], str(real_request.pk))
        self.assertNotIn(learner.email, str(result.data))
        self.client.force_authenticate(self.outsider)
        self.assertEqual(
            self.client.get(row["links"]["request_detail"]).status_code, 404
        )

    def test_services_separates_requests_cases_and_offers(self):
        self.space.archetype = SpaceArchetype.SERVICE_PROVIDER
        self.space.save(update_fields=["archetype", "updated_at"])
        service = self.activity("Accompagnement administratif")
        ServiceDetails.objects.create(
            activity=service, service_kind=ServiceKind.ADMINISTRATIVE_SUPPORT,
        )
        beneficiary = self.beneficiary("group2-service-client")
        request = Journey.objects.create(
            initiated_by=beneficiary, beneficiary=beneficiary, activity=service,
            workflow=WorkflowKind.SERVICE, status=JourneyStatus.SUBMITTED,
        )
        active = Journey.objects.create(
            initiated_by=beneficiary, beneficiary=beneficiary, activity=service,
            workflow=WorkflowKind.SERVICE, status=JourneyStatus.IN_PROGRESS,
        )
        ServiceJourneyContext.objects.create(
            journey=active, objective="Motif confidentiel",
        )
        operator = self.beneficiary("group2-case-operator")
        grant_activity_role(
            profile=operator, activity=service,
            role_code=SystemRoleCode.ACTIVITY_SERVICE_MANAGER,
            granted_by=self.owner,
        )
        self.client.force_authenticate(operator)
        result = self.client.get(self.url)
        self.assertEqual(result.status_code, 200, result.data)
        self.assertEqual(
            [g["identity"] for g in result.data["business_world"]["reading_groups"]],
            ["requests", "cases", "portfolio"],
        )
        self.assertEqual(result.data["presentation"]["section_order"],
                         ["requests", "active", "activities"])
        self.assertEqual(
            result.data["sections"]["requests"]["items"][0]["source"]["id"],
            str(request.pk),
        )
        case = result.data["sections"]["active"]["items"][0]
        self.assertEqual(case["source"]["id"], str(active.pk))
        self.assertEqual(case["context"]["work_label"], "Dossier de prestation")
        self.assertEqual(case["context"]["service_outcome"], "not_submitted")
        self.assertNotIn("conditions", case["context"])
        self.assertIn("open_service_case", case["capabilities"])
        self.assertIn("/services/operator/journeys/", case["links"]["detail"])
        self.assertNotIn(beneficiary.email, str(result.data))
        self.assertNotIn("Motif confidentiel", str(result.data))
        self.client.force_authenticate(self.outsider)
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_real_services_conditions_are_aggregated_without_notes(self):
        self.space.archetype = SpaceArchetype.SERVICE_PROVIDER
        self.space.save(update_fields=["archetype", "updated_at"])
        activity = self.activity("Prestations conditionnelles")
        ServiceDetails.objects.create(
            activity=activity, service_kind=ServiceKind.ADMINISTRATIVE_SUPPORT,
            opportunity_policy=OpportunityPolicy.OPTIONAL,
        )
        opportunity = Opportunity.objects.create(
            kind=OpportunityKind.OTHER, created_by=self.owner,
        )
        revision = OpportunityRevision.objects.create(
            opportunity=opportunity, version=1, title="Référence externe",
            issuer_name="Institution", timezone="UTC",
        )
        accepted = OpportunityRequirement.objects.create(
            revision=revision, kind=OpportunityRequirementKind.DOCUMENT,
            title="Document confidentiel", position=0,
        )
        pending = OpportunityRequirement.objects.create(
            revision=revision, kind=OpportunityRequirementKind.OTHER,
            title="Autre exigence confidentielle", position=1,
        )
        revision.published_at = timezone.now()
        revision._allow_publication = True
        revision.save(update_fields=["published_at"])
        beneficiary = self.beneficiary("group2-private-assessment")
        case = Journey.objects.create(
            initiated_by=beneficiary, beneficiary=beneficiary, activity=activity,
            workflow=WorkflowKind.SERVICE, status=JourneyStatus.IN_PROGRESS,
        )
        context = ServiceJourneyContext.objects.create(
            journey=case, opportunity=opportunity, opportunity_revision=revision,
            objective="Objectif confidentiel",
        )
        ServiceRequirementAssessment.objects.create(
            context=context, requirement=accepted,
            status=RequirementAssessmentState.SATISFIED,
            assessed_by=self.owner, assessed_at=timezone.now(),
            note="Commentaire privé",
        )
        ServiceRequirementAssessment.objects.create(
            context=context, requirement=pending,
            status=RequirementAssessmentState.UNASSESSED,
        )
        operator = self.beneficiary("group2-assessment-operator")
        grant_activity_role(
            profile=operator, activity=activity,
            role_code=SystemRoleCode.ACTIVITY_SERVICE_MANAGER,
            granted_by=self.owner,
        )
        self.client.force_authenticate(operator)
        result = self.client.get(self.url)
        self.assertEqual(result.status_code, 200, result.data)
        row = result.data["sections"]["active"]["items"][0]
        self.assertEqual(row["context"]["conditions"], {
            "total": 2, "satisfied": 1, "awaiting": 1, "unsatisfied": 0,
            "basis": "service_requirement_assessment",
        })
        self.assertNotIn("Commentaire privé", str(result.data))
        self.assertNotIn("Document confidentiel", str(result.data))
        self.assertNotIn(beneficiary.email, str(result.data))
        self.client.force_authenticate(self.outsider)
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_web_programme_first_and_next_real_session(self):
        self.space.archetype = SpaceArchetype.EDUCATION
        self.space.save(update_fields=["archetype", "updated_at"])
        programme = self.activity("Programme de langues")
        Occurrence.objects.create(
            activity=programme, label="Session linguistique",
            start_at=timezone.now() + timedelta(days=4),
            status=OccurrenceStatus.SCHEDULED,
        )
        self.web.force_login(self.owner)
        response = self.web.get("/spaces/group-2/work/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nos programmes")
        self.assertContains(response, "Sessions et préparation")
        self.assertContains(response, "Prochaine session")
        self.assertContains(response, "Session linguistique")
        self.assertEqual(
            [section["key"] for section in response.context["work_sections"]],
            ["activities", "upcoming"],
        )

    def test_web_case_handoff_is_owner_backed_without_private_summary(self):
        self.space.archetype = SpaceArchetype.SERVICE_PROVIDER
        self.space.save(update_fields=["archetype", "updated_at"])
        activity = self.activity("Prestation personnalisée")
        ServiceDetails.objects.create(
            activity=activity, service_kind=ServiceKind.ADMINISTRATIVE_SUPPORT,
        )
        client = self.beneficiary("group2-web-beneficiary")
        case = Journey.objects.create(
            initiated_by=client, beneficiary=client, activity=activity,
            workflow=WorkflowKind.SERVICE, status=JourneyStatus.IN_PROGRESS,
        )
        ServiceJourneyContext.objects.create(
            journey=case, objective="Contenu confidentiel",
        )
        operator = self.beneficiary("group2-web-operator")
        grant_activity_role(
            profile=operator, activity=activity,
            role_code=SystemRoleCode.ACTIVITY_SERVICE_MANAGER,
            granted_by=self.owner,
        )
        self.web.force_login(operator)
        response = self.web.get("/spaces/group-2/work/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dossiers à accompagner")
        self.assertContains(response, "Prestations proposées")
        self.assertContains(response, "Dossier de prestation")
        self.assertContains(response, "Ouvrir le dossier")
        self.assertContains(response, f"/services/operator/journeys/{case.pk}/")
        self.assertNotContains(response, client.email)
        self.assertNotContains(response, "Contenu confidentiel")

    def test_other_archetypes_keep_existing_contract(self):
        self.space.archetype = SpaceArchetype.CREATIVE
        self.space.save(update_fields=["archetype", "updated_at"])
        self.activity("Création principale")
        self.client.force_authenticate(self.owner)
        result = self.client.get(self.url)
        self.assertEqual(result.status_code, 200, result.data)
        self.assertNotIn("business_world", result.data)
        self.assertNotIn("reading_groups", result.data["presentation"])
