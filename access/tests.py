from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.utils import timezone

from activities.models import Activity, Occurrence
from journeys.models import JourneyStatus, WorkflowKind
from journeys.services import (
    approve_request,
    confirm_journey,
    create_journey,
    create_request,
    submit_journey,
)

from .models import (
    Access,
    AccessStatus,
    AccessUseResult,
    CredentialStatus,
    CredentialType,
)
from .services import (
    cancel_access,
    expire_access,
    issue_access,
    render_access_credential,
    revoke_access,
    rotate_access_credential,
    validate_access_credential,
)


User = get_user_model()


class AccessFixtureMixin:
    def build_fixture(self):
        self.owner = User.objects.create_user(
            username="access-owner",
            email="access-owner@example.com",
            password="Access-2026!",
        )
        self.other = User.objects.create_user(
            username="access-other",
            email="access-other@example.com",
            password="Access-2026!",
        )
        self.decider = User.objects.create_superuser(
            username="access-decider",
            email="access-decider@example.com",
            password="Access-2026!",
        )
        self.activity = Activity.objects.create(created_by=self.owner, title="Access Activity")
        now = timezone.now()
        self.occurrence = Occurrence.objects.create(
            activity=self.activity,
            start_at=now - timedelta(hours=1),
            end_at=now + timedelta(hours=2),
        )

    def journey(self, workflow=WorkflowKind.REGISTRATION):
        return create_journey(
            initiated_by=self.owner,
            beneficiary=self.owner,
            activity=self.activity,
            occurrence=self.occurrence,
            workflow=workflow,
        )


class AccessServiceTests(AccessFixtureMixin, TestCase):
    def setUp(self):
        self.build_fixture()

    def test_issue_access_is_individual_idempotent_and_creates_credential(self):
        journey = self.journey()
        first = issue_access(
            beneficiary=self.owner,
            activity=self.activity,
            occurrence=self.occurrence,
            journey=journey,
            source_key="registration:primary",
        )
        second = issue_access(
            beneficiary=self.owner,
            activity=self.activity,
            occurrence=self.occurrence,
            journey=journey,
            source_key="registration:primary",
        )
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Access.objects.count(), 1)
        self.assertEqual(first.credentials.filter(status=CredentialStatus.ACTIVE).count(), 1)
        self.assertEqual(first.beneficiary, self.owner)

        with self.assertRaises(ValidationError):
            issue_access(
                beneficiary=None,
                activity=self.activity,
                occurrence=self.occurrence,
            )

    def test_access_can_exist_without_journey_or_payment(self):
        access = issue_access(
            beneficiary=self.owner,
            activity=self.activity,
            occurrence=None,
            journey=None,
            valid_from=None,
            valid_until=None,
        )
        self.assertIsNone(access.journey_id)
        self.assertIsNone(access.occurrence_id)
        self.assertEqual(access.status, AccessStatus.VALID)

    def test_credential_authenticity_rotation_and_revocation(self):
        access = issue_access(
            beneficiary=self.owner,
            activity=self.activity,
            occurrence=self.occurrence,
            source_key="rotation",
        )
        old = access.credentials.get(status=CredentialStatus.ACTIVE)
        old_token = render_access_credential(old)

        new = rotate_access_credential(access=access)
        old.refresh_from_db()
        self.assertEqual(old.status, CredentialStatus.REVOKED)
        self.assertEqual(new.version, old.version + 1)

        old_outcome = validate_access_credential(old_token)
        self.assertEqual(old_outcome.result, AccessUseResult.REVOKED)

        new_token = render_access_credential(new)
        tampered = new_token[:-1] + ("x" if new_token[-1] != "x" else "y")
        self.assertEqual(
            validate_access_credential(tampered).result,
            AccessUseResult.INVALID_CREDENTIAL,
        )

    def test_wrong_credential_type_is_rejected(self):
        access = issue_access(
            beneficiary=self.owner,
            activity=self.activity,
            occurrence=self.occurrence,
            create_credential=False,
        )
        barcode = access.credentials.create(
            credential_type=CredentialType.BARCODE,
            version=1,
        )
        token = render_access_credential(barcode)
        self.assertEqual(
            validate_access_credential(token).result,
            AccessUseResult.INVALID_CREDENTIAL,
        )

    def test_single_use_and_scope_validation(self):
        access = issue_access(
            beneficiary=self.owner,
            activity=self.activity,
            occurrence=self.occurrence,
        )
        token = render_access_credential(access.credentials.get(status=CredentialStatus.ACTIVE))
        first = validate_access_credential(
            token,
            expected_activity=self.activity,
            expected_occurrence=self.occurrence,
        )
        second = validate_access_credential(
            token,
            expected_activity=self.activity,
            expected_occurrence=self.occurrence,
        )
        self.assertEqual(first.result, AccessUseResult.ACCEPTED)
        self.assertEqual(second.result, AccessUseResult.ALREADY_USED)

        other_activity = Activity.objects.create(created_by=self.owner, title="Wrong Activity")
        other_occurrence = Occurrence.objects.create(
            activity=other_activity,
            start_at=timezone.now() - timedelta(minutes=10),
            end_at=timezone.now() + timedelta(hours=1),
        )
        other_access = issue_access(
            beneficiary=self.owner,
            activity=self.activity,
            occurrence=self.occurrence,
        )
        other_token = render_access_credential(other_access.credentials.get(status=CredentialStatus.ACTIVE))
        self.assertEqual(
            validate_access_credential(other_token, expected_activity=other_activity).result,
            AccessUseResult.WRONG_ACTIVITY,
        )

        second_occurrence = Occurrence.objects.create(
            activity=self.activity,
            start_at=timezone.now() - timedelta(minutes=5),
            end_at=timezone.now() + timedelta(hours=1),
        )
        scoped = issue_access(
            beneficiary=self.owner,
            activity=self.activity,
            occurrence=self.occurrence,
        )
        scoped_token = render_access_credential(scoped.credentials.get(status=CredentialStatus.ACTIVE))
        self.assertEqual(
            validate_access_credential(scoped_token, expected_occurrence=second_occurrence).result,
            AccessUseResult.WRONG_OCCURRENCE,
        )

    def test_validity_expiration_revoke_and_cancel(self):
        now = timezone.now()
        future_access = issue_access(
            beneficiary=self.owner,
            activity=self.activity,
            occurrence=None,
            valid_from=now + timedelta(hours=1),
            valid_until=now + timedelta(hours=2),
        )
        future_token = render_access_credential(
            future_access.credentials.get(status=CredentialStatus.ACTIVE)
        )
        self.assertEqual(
            validate_access_credential(future_token, now=now).result,
            AccessUseResult.NOT_YET_VALID,
        )

        expiring = issue_access(
            beneficiary=self.owner,
            activity=self.activity,
            occurrence=None,
            valid_from=now - timedelta(hours=2),
            valid_until=now + timedelta(seconds=1),
        )
        expire_access(access=expiring, now=now + timedelta(minutes=1))
        expiring.refresh_from_db()
        self.assertEqual(expiring.status, AccessStatus.EXPIRED)
        self.assertFalse(expiring.credentials.filter(status=CredentialStatus.ACTIVE).exists())

        revoked = issue_access(beneficiary=self.owner, activity=self.activity, occurrence=None)
        revoked_token = render_access_credential(revoked.credentials.get(status=CredentialStatus.ACTIVE))
        revoke_access(access=revoked)
        self.assertEqual(validate_access_credential(revoked_token).result, AccessUseResult.REVOKED)

        cancelled = issue_access(beneficiary=self.owner, activity=self.activity, occurrence=None)
        cancelled_token = render_access_credential(cancelled.credentials.get(status=CredentialStatus.ACTIVE))
        cancel_access(access=cancelled)
        self.assertEqual(
            validate_access_credential(cancelled_token).result,
            AccessUseResult.REVOKED,
        )

    def test_participant_cannot_administer_access(self):
        access = issue_access(beneficiary=self.owner, activity=self.activity, occurrence=None)
        with self.assertRaises(PermissionDenied):
            revoke_access(access=access, actor=self.other)

    def test_activity_occurrence_and_journey_consistency(self):
        other_activity = Activity.objects.create(created_by=self.owner, title="Other Access Activity")
        other_occurrence = Occurrence.objects.create(
            activity=other_activity,
            start_at=timezone.now(),
            end_at=timezone.now() + timedelta(hours=1),
        )
        with self.assertRaises(ValidationError):
            issue_access(
                beneficiary=self.owner,
                activity=self.activity,
                occurrence=other_occurrence,
            )

        journey = self.journey()
        with self.assertRaises(ValidationError):
            issue_access(
                beneficiary=self.owner,
                activity=other_activity,
                occurrence=other_occurrence,
                journey=journey,
            )


class FreeJourneyAccessTests(AccessFixtureMixin, TestCase):
    def setUp(self):
        self.build_fixture()

    def test_registration_reservation_and_invitation_issue_access_without_order_or_payment(self):
        from payments.models import Payment
        from tickets.models import TicketOrder

        for workflow in (WorkflowKind.REGISTRATION, WorkflowKind.RESERVATION):
            journey = self.journey(workflow)
            submit_journey(journey=journey, actor=self.owner)
            confirm_journey(journey=journey)
            access = issue_access(
                beneficiary=self.owner,
                activity=self.activity,
                occurrence=self.occurrence,
                journey=journey,
                source_key=f"{workflow}:result",
            )
            self.assertEqual(access.status, AccessStatus.VALID)

        invitation = self.journey(WorkflowKind.INVITATION)
        submit_journey(journey=invitation, actor=self.owner)
        request = create_request(journey=invitation, requester=self.owner)
        approve_request(request=request, actor=self.decider)
        confirm_journey(journey=invitation)
        invitation_access = issue_access(
            beneficiary=self.owner,
            activity=self.activity,
            occurrence=self.occurrence,
            journey=invitation,
            source_key="invitation:result",
        )
        self.assertEqual(invitation_access.status, AccessStatus.VALID)
        self.assertEqual(TicketOrder.objects.count(), 0)
        self.assertEqual(Payment.objects.count(), 0)
