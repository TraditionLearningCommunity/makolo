from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from activities.models import ActivityStatus, ActivityVisibility
from authorization.constants import SystemRoleCode
from authorization.services import grant_space_role
from journeys.models import JourneyStatus, WorkflowKind
from organizations.models import Organization
from readiness import ReadinessStatus, resolve_journey_readiness

from .models import ObtentionConfigurationStatus, ObtentionModeCode
from .selectors import fulfillment_for_journey
from .services import (
    activate_obtention_journey,
    create_obtention,
    create_obtention_journey,
    fulfill_obtention_journey,
    record_beneficiary_receipt,
    record_operator_receipt,
    revise_obtention,
)


User = get_user_model()


class ObtentionCoreTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="obtention-owner",
            email="obtention-owner@example.test",
            password="test-pass",
        )
        self.beneficiary = User.objects.create_user(
            username="obtention-beneficiary",
            email="obtention-beneficiary@example.test",
            password="test-pass",
        )
        self.outsider = User.objects.create_user(
            username="obtention-outsider",
            email="obtention-outsider@example.test",
            password="test-pass",
        )
        self.obtention = create_obtention(
            actor=self.owner,
            title="Kit scolaire rentrée",
            short_description="Obtenir un kit complet.",
            targets=[
                {"title": "Sac", "quantity": "1", "unit": "pièce"},
                {"title": "Cahiers", "quantity": "10", "unit": "pièces"},
            ],
            modes=[ObtentionModeCode.RECEIVE],
            result_label="Kit scolaire effectivement remis",
            operator_confirmation_required=True,
            status=ActivityStatus.PUBLISHED,
            visibility=ActivityVisibility.PUBLIC,
        )

    def _configuration(self):
        return self.obtention.configurations.get(
            status=ObtentionConfigurationStatus.PUBLISHED
        )

    def _journey(self):
        journey = create_obtention_journey(
            obtention=self.obtention,
            actor=self.beneficiary,
            mode=ObtentionModeCode.RECEIVE,
        )
        return activate_obtention_journey(journey=journey, actor=self.beneficiary)

    def test_vertical_keeps_activity_generic_and_has_real_target_and_mode(self):
        configuration = self._configuration()
        self.assertEqual(self.obtention.activity.obtention_details, self.obtention)
        self.assertEqual(configuration.targets.count(), 2)
        self.assertEqual(
            list(configuration.modes.values_list("code", flat=True)),
            [ObtentionModeCode.RECEIVE],
        )
        self.assertFalse(hasattr(self.obtention, "payment"))
        self.assertFalse(hasattr(self.obtention, "order"))

    def test_obtention_requires_target_and_mode(self):
        with self.assertRaises(ValidationError):
            create_obtention(
                actor=self.owner,
                title="Sans cible",
                targets=[],
                modes=[ObtentionModeCode.RECEIVE],
                result_label="Reçu",
            )
        with self.assertRaises(ValidationError):
            create_obtention(
                actor=self.owner,
                title="Sans mode",
                targets=[{"title": "Objet"}],
                modes=[],
                result_label="Reçu",
            )

    def test_revision_versions_contract_without_changing_existing_journey(self):
        journey = self._journey()
        pinned_version = journey.obtention_context.configuration.version
        revise_obtention(
            obtention=self.obtention,
            actor=self.owner,
            title="Kit scolaire rentrée",
            targets=[
                {"title": "Sac", "quantity": "1"},
                {"title": "Cahiers", "quantity": "12"},
                {"title": "Uniforme", "quantity": "1"},
            ],
            modes=[ObtentionModeCode.RECEIVE],
            result_label="Nouveau kit remis",
            status=ActivityStatus.PUBLISHED,
            visibility=ActivityVisibility.PUBLIC,
        )
        journey.refresh_from_db()
        self.assertEqual(journey.obtention_context.configuration.version, pinned_version)
        current = self._configuration()
        self.assertEqual(current.version, pinned_version + 1)
        self.assertEqual(current.targets.count(), 3)

    def test_payment_or_confirmation_state_alone_cannot_fulfill_without_receipt(self):
        journey = self._journey()
        self.assertEqual(journey.status, JourneyStatus.CONFIRMED)
        with self.assertRaises(ValidationError):
            fulfill_obtention_journey(journey=journey, actor=self.beneficiary)
        journey.refresh_from_db()
        self.assertEqual(journey.status, JourneyStatus.CONFIRMED)
        self.assertEqual(resolve_journey_readiness(journey).status, ReadinessStatus.ACTION_REQUIRED)

    def test_actual_receipts_and_required_confirmations_allow_fulfillment(self):
        journey = self._journey()
        targets = list(journey.obtention_context.configuration.targets.all())
        for target in targets:
            record_beneficiary_receipt(
                journey=journey,
                target=target,
                actor=self.beneficiary,
                received_quantity=target.quantity,
            )
            record_operator_receipt(
                journey=journey,
                target=target,
                actor=self.owner,
            )
        journey.refresh_from_db()
        result = fulfillment_for_journey(journey)
        self.assertTrue(result.complete)
        self.assertEqual(resolve_journey_readiness(journey).status, ReadinessStatus.READY)
        fulfilled = fulfill_obtention_journey(journey=journey, actor=self.beneficiary)
        self.assertEqual(fulfilled.status, JourneyStatus.FULFILLED)

    def test_outsider_cannot_confirm_operator_receipt(self):
        journey = self._journey()
        target = journey.obtention_context.configuration.targets.first()
        with self.assertRaises(PermissionDenied):
            record_operator_receipt(
                journey=journey,
                target=target,
                actor=self.outsider,
                received_quantity=target.quantity,
            )

    def test_beneficiary_only_can_confirm_own_receipt(self):
        journey = self._journey()
        target = journey.obtention_context.configuration.targets.first()
        with self.assertRaises(PermissionDenied):
            record_beneficiary_receipt(
                journey=journey,
                target=target,
                actor=self.outsider,
                received_quantity=target.quantity,
            )

    def test_non_purchase_modes_use_generic_fulfillment_not_purchase(self):
        journey = self._journey()
        self.assertEqual(journey.workflow, WorkflowKind.FULFILLMENT)
        self.assertNotEqual(journey.workflow, WorkflowKind.PURCHASE)


class ObtentionSpaceAuthorityTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="obtention-space-owner",
            email="obtention-space-owner@example.test",
            password="test-pass",
        )
        self.member = User.objects.create_user(
            username="obtention-space-member",
            email="obtention-space-member@example.test",
            password="test-pass",
        )
        self.space = Organization.objects.create(
            name="Espace Obtention",
            created_by=self.owner,
        )

    def _create(self, actor):
        return create_obtention(
            actor=actor,
            space=self.space,
            title="Distribution",
            targets=[{"title": "Kit"}],
            modes=[ObtentionModeCode.RECEIVE],
            result_label="Kit remis",
        )

    def test_space_membership_or_context_without_mandate_is_not_authority(self):
        with self.assertRaises(PermissionDenied):
            self._create(self.member)

    def test_space_owner_mandate_can_create_obtention(self):
        grant_space_role(
            profile=self.owner,
            space=self.space,
            role=SystemRoleCode.SPACE_OWNER,
            granted_by=self.owner,
            source="obtention-test",
        )
        obtention = self._create(self.owner)
        self.assertEqual(obtention.activity.space, self.space)
        self.assertIsNone(obtention.activity.owner_profile_id)
