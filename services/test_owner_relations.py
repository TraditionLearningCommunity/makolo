from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import TestCase

from activities.models import Activity
from opportunities.models import OpportunityKind, OpportunitySourceType
from opportunities.services import (
    create_opportunity,
    create_opportunity_revision,
    create_opportunity_source,
    publish_opportunity_revision,
)

from .models import OpportunityPolicy, ServiceDetails, ServiceKind
from .selectors import service_opportunity_relation_for_viewer
from .services import create_service_journey


class ServiceOpportunityRelationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.curator = User.objects.create_user(
            username="relation-curator", email="relation-curator@example.test",
            password="test-pass-2026", is_staff=True, is_superuser=True,
        )
        self.beneficiary = User.objects.create_user(
            username="relation-beneficiary", email="relation-beneficiary@example.test",
            password="test-pass-2026",
        )
        self.outsider = User.objects.create_user(
            username="relation-outsider", email="relation-outsider@example.test",
            password="test-pass-2026",
        )
        activity = Activity.objects.create(
            owner_profile=self.curator, created_by=self.curator,
            title="Opportunity support",
        )
        self.service = ServiceDetails.objects.create(
            activity=activity, service_kind=ServiceKind.APPLICATION_SUPPORT,
            opportunity_policy=OpportunityPolicy.OPTIONAL,
        )
        self.opportunity = create_opportunity(
            actor=self.curator, kind=OpportunityKind.SCHOLARSHIP,
        )
        self.revision = create_opportunity_revision(
            opportunity=self.opportunity, actor=self.curator,
            title="Real external opportunity", issuer_name="External issuer",
            timezone_name="Africa/Lubumbashi",
        )
        create_opportunity_source(
            opportunity=self.opportunity, actor=self.curator,
            source_type=OpportunitySourceType.OFFICIAL,
            source_name="Official source", url="https://example.test/opportunity",
            is_primary=True,
        )
        publish_opportunity_revision(
            opportunity=self.opportunity, revision=self.revision,
            actor=self.curator,
        )
        self.journey = create_service_journey(
            service=self.service, initiated_by=self.beneficiary,
            beneficiary=self.beneficiary, opportunity=self.opportunity,
        )

    def test_beneficiary_sees_existing_relation_with_pinned_revision(self):
        relation = service_opportunity_relation_for_viewer(
            journey_id=self.journey.pk, viewer=self.beneficiary,
        )
        self.assertEqual(relation["kind"], "service_journey_opportunity")
        self.assertEqual(
            relation["members"],
            [
                {"kind": "journey", "id": str(self.journey.pk)},
                {"kind": "opportunity", "id": str(self.opportunity.pk)},
            ],
        )
        self.assertEqual(relation["revision"]["id"], str(self.revision.pk))
        self.assertEqual(
            relation["basis"]["id"], str(self.journey.service_context.pk)
        )
        self.assertNotIn("authority", relation)
        self.assertNotIn("access", relation)

    def test_outsider_and_guest_do_not_see_private_relation(self):
        self.assertIsNone(service_opportunity_relation_for_viewer(
            journey_id=self.journey.pk, viewer=AnonymousUser(),
        ))
        self.assertIsNone(service_opportunity_relation_for_viewer(
            journey_id=self.journey.pk, viewer=self.outsider,
        ))

    def test_service_without_explicit_opportunity_has_no_relation(self):
        other = create_service_journey(
            service=self.service, initiated_by=self.beneficiary,
            beneficiary=self.beneficiary,
        )
        self.assertIsNone(service_opportunity_relation_for_viewer(
            journey_id=other.pk, viewer=self.beneficiary,
        ))
