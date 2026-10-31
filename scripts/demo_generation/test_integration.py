"""Validation is run with Django's isolated test database, not demo SQLite.

The suite verifies canonical service invariants and CLI scheduling. Existing
domain suites are reused instead of duplicating complex business fixtures.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.core.exceptions import ValidationError
from decimal import Decimal

from activities.models import ActivityStatus, ActivityVisibility
from funding.models import FundingContribution, FundingDetails
from funding.services import create_funding, create_funding_contribution
from payments.obligation_services import satisfy_payment_obligation
from payments.models import PaymentObligationStatus
from scripts.demo_generation.scale import distributed_pairs


class DemoIntegrationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(
            username="world_demo_validator_owner",
            email="demo-validator-owner@example.test",
            password="example-only-not-a-real-password",
        )
        self.beneficiary = User.objects.create_user(
            username="world_demo_validator_person",
            email="demo-validator-person@example.test",
            password="example-only-not-a-real-password",
        )

    def test_funding_is_an_activity_and_contribution_is_idempotent(self):
        funding = create_funding(
            actor=self.owner, title="[DEMO] Fournitures scolaires",
            description="Scenario fictif de validation",
            currency="USD", target_amount=Decimal("100.00"),
            minimum_contribution=Decimal("1.00"),
            status=ActivityStatus.PUBLISHED,
            visibility=ActivityVisibility.PUBLIC,
        )
        self.assertIsInstance(funding, FundingDetails)
        self.assertEqual(funding.activity.status, ActivityStatus.PUBLISHED)
        first = create_funding_contribution(
            funding=funding, actor=self.beneficiary,
            amount=Decimal("12.50"), client_reference="validate-funding-1",
        )
        repeated = create_funding_contribution(
            funding=funding, actor=self.beneficiary,
            amount=Decimal("12.50"), client_reference="validate-funding-1",
        )
        self.assertEqual(first.pk, repeated.pk)
        self.assertEqual(FundingContribution.objects.filter(funding=funding).count(), 1)
        self.assertNotEqual(first.payment_obligation.status, PaymentObligationStatus.SATISFIED)
        satisfy_payment_obligation(
            obligation=first.payment_obligation, source="synthetic-demo-validation",
        )
        first.payment_obligation.refresh_from_db()
        self.assertEqual(first.payment_obligation.status, PaymentObligationStatus.SATISFIED)

    def test_reference_distribution_is_bounded_unique_and_fair(self):
        occurrences = ["live-1", "live-2", "live-3"]
        profiles = ["world-a", "world-b"]
        candidates = list(distributed_pairs(occurrences, profiles, 6))
        self.assertEqual(len(candidates), 6)
        self.assertEqual(len(set(candidates)), 6)
        self.assertEqual([x[0] for x in candidates[:3]], occurrences)
        self.assertEqual(list(distributed_pairs(occurrences, [], 10)), [])

    def test_funding_rejects_non_positive_amount(self):
        funding = create_funding(
            actor=self.owner, title="[DEMO] Action locale",
            currency="USD", target_amount=Decimal("100.00"),
            minimum_contribution=Decimal("1.00"),
            status=ActivityStatus.PUBLISHED,
            visibility=ActivityVisibility.PUBLIC,
        )
        with self.assertRaises(ValidationError):
            create_funding_contribution(
                funding=funding, actor=self.beneficiary,
                amount=Decimal("0"), client_reference="validate-bad-amount",
            )

    def test_group_membership_does_not_grant_global_authority(self):
        from groups.services import create_group, add_member
        from groups.models import GroupMembership
        from authorization.models import Mandate
        group = create_group(
            actor=self.owner, name="[DEMO] Groupe d'entraide",
            description="Adhesions synthetiques pour validation",
        )
        member, created = add_member(
            actor=self.owner, group=group, profile=self.beneficiary,
        )
        self.assertTrue(created)
        self.assertIsInstance(member, GroupMembership)
        repeated, created_again = add_member(
            actor=self.owner, group=group, profile=self.beneficiary,
        )
        self.assertEqual(member.pk, repeated.pk)
        self.assertFalse(created_again)
        self.assertFalse(Mandate.objects.filter(profile=self.beneficiary).exists())

    def test_personal_objective_is_composed_without_new_authority(self):
        from objectives.services import create_dossier, create_project, link_dossier_to_project
        from objectives.models import ProjectDossierLink
        project = create_project(
            actor=self.owner, owner_profile=self.owner,
            title="[DEMO] Horizon educatif",
        )
        dossier = create_dossier(
            actor=self.owner, owner_profile=self.owner,
            title="[DEMO] Fournitures pour cette annee",
        )
        first = link_dossier_to_project(
            actor=self.owner, project=project, dossier=dossier,
        )
        second = link_dossier_to_project(
            actor=self.owner, project=project, dossier=dossier,
        )
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(ProjectDossierLink.objects.filter(
            project=project, dossier=dossier, is_active=True).count(), 1)
