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

    def test_service_manager_creates_service_and_journey_bound_form(self):
        from activities.services import create_activity
        from authorization.constants import SystemRoleCode
        from authorization.services import grant_activity_role
        from services.models import ServiceKind, ServiceDetails
        from services.services import create_service_details, create_service_journey
        from questionnaires.models import Form, FormRequest, FormVersionStatus, QuestionType
        from questionnaires.services import (
            create_form, create_form_version, add_question,
            publish_form_version, request_form,
        )
        activity = create_activity(
            created_by=self.owner, owner_profile=self.owner,
            title="[DEMO] Accompagnement",
            status=ActivityStatus.PUBLISHED,
        )
        grant_activity_role(
            profile=self.owner, activity=activity,
            role=SystemRoleCode.ACTIVITY_SERVICE_MANAGER,
            granted_by=self.owner, source="demo-validation",
        )
        service = create_service_details(
            activity=activity, actor=self.owner,
            service_kind=ServiceKind.ADMINISTRATIVE_SUPPORT,
        )
        self.assertIsInstance(service, ServiceDetails)
        journey = create_service_journey(
            service=service, initiated_by=self.beneficiary,
            beneficiary=self.beneficiary, objective="Préparer mon dossier",
        )
        form = create_form(
            activity=activity, actor=self.owner,
            key="demo-preparation", title="Préparation",
        )
        version = create_form_version(form=form, actor=self.owner)
        add_question(
            form_version=version, actor=self.owner,
            key="notes", label="Notes utiles",
            question_type=QuestionType.LONG_TEXT,
            position=1, required=False,
        )
        publish_form_version(form_version=version, actor=self.owner)
        self.assertEqual(version.status, FormVersionStatus.PUBLISHED)
        request = request_form(
            form_version=version, journey=journey,
            actor=self.owner, required=False,
        )
        self.assertEqual(request.journey_id, journey.pk)
        self.assertEqual(Form.objects.filter(activity=activity).count(), 1)
        self.assertEqual(FormRequest.objects.filter(journey=journey).count(), 1)

    def test_demo_connections_are_real_local_rows_without_external_credentials(self):
        from django.core.exceptions import ValidationError
        from intelligence.demo_connections import demo_offers, create_demo_connection
        from intelligence.connection_management import update_connection
        from intelligence.models import ProviderScope, ProviderCredential, IntelligenceRoute
        from intelligence.interoperability import project_provider_connection
        self.assertEqual(len(demo_offers()), 50)
        self.assertTrue(all("demo" not in offer["label"].lower() and
                            "simulation" not in offer["description"].lower()
                            for offer in demo_offers()))
        code = demo_offers()[0]["code"]
        connection, created = create_demo_connection(
            actor=self.owner, scope=ProviderScope.PROFILE,
            provider=code, consent=True,
        )
        self.assertTrue(created)
        repeated, created_again = create_demo_connection(
            actor=self.owner, scope=ProviderScope.PROFILE,
            provider=code, consent=True,
        )
        self.assertFalse(created_again)
        self.assertEqual(connection.pk, repeated.pk)
        self.assertFalse(connection.enabled)
        self.assertFalse(ProviderCredential.objects.filter(connection=connection).exists())
        self.assertEqual(IntelligenceRoute.objects.filter(connection=connection, enabled=False).count(), 1)
        projected = project_provider_connection(connection, manageable=True)
        self.assertTrue(projected["demo"])
        self.assertFalse(projected["usable"])
        self.assertTrue(projected["connected"])
        self.assertFalse(projected["external_execution"])
        self.assertNotIn("[DEMO", projected["display_name"])
        # Older beta records carry a visible prefix. A new run must reuse
        # them without creating a second connection for the same owner.
        connection.name = "[DEMO Connexion] " + connection.name
        connection.default_model = ""
        connection.save(update_fields=["name", "default_model", "updated_at"])
        restored, was_created = create_demo_connection(
            actor=self.owner, scope=ProviderScope.PROFILE,
            provider=code, consent=True,
        )
        self.assertFalse(was_created)
        self.assertEqual(restored.pk, connection.pk)
        self.assertEqual(restored.default_model, "demo-disabled")
        self.assertEqual(restored.name, demo_offers()[0]["label"])
        with self.assertRaises(ValidationError):
            update_connection(actor=self.owner, connection=connection, payload={"enabled": True})
        with self.assertRaises(ValidationError):
            create_demo_connection(actor=self.beneficiary, scope=ProviderScope.PROFILE,
                                   provider=code, consent=False)

    def test_contextual_conversation_point_is_idempotent(self):
        from activities.services import create_activity
        from conversations.core_models import ConversationContextKind, ConversationModePreset
        from conversations.point_models import ConversationPointKind, ConversationPointResponseMode, ConversationPoint
        from conversations.services import ensure_context_conversation
        from conversations.point_services import create_point
        activity = create_activity(
            created_by=self.owner, owner_profile=self.owner,
            title="[DEMO] Atelier de preparation", status=ActivityStatus.PUBLISHED,
        )
        kw = dict(actor=self.owner, kind=ConversationContextKind.ACTIVITY,
                  activity=activity, purpose_key="demo-preparation",
                  separation_reason="Échanges de préparation distincts de la coordination de l'activité.",
                  mode_preset=ConversationModePreset.MIXED)
        conversation = ensure_context_conversation(**kw)
        self.assertEqual(conversation.pk, ensure_context_conversation(**kw).pk)
        point_kw = dict(
            actor=self.owner, conversation=conversation,
            kind=ConversationPointKind.QUESTION,
            response_mode=ConversationPointResponseMode.FREE_TEXT,
            title="Preparation", body="Que faut-il clarifier?",
            client_reference="demo-conv-test-unique-point",
        )
        first = create_point(**point_kw)
        self.assertEqual(first.pk, create_point(**point_kw).pk)
        self.assertEqual(ConversationPoint.objects.filter(
            conversation=conversation).count(), 1)
