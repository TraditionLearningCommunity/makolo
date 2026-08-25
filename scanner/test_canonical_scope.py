from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.utils import timezone

from access.models import AccessUse, AccessUseResult, CredentialStatus
from access.services import issue_access, render_access_credential
from activities.models import Activity, Occurrence
from authorization.constants import PermissionCode, SystemRoleCode
from authorization.services import can, grant_activity_role

from .canonical_services import scan_access_credential
from .models import ScanLog, ScannerAssignment


User = get_user_model()


class CanonicalScannerScopeTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("scan-owner", "scan-owner@example.com", "Scan-2026!")
        self.agent = User.objects.create_user("scan-agent", "scan-agent@example.com", "Scan-2026!")
        self.other = User.objects.create_user("scan-other", "scan-other@example.com", "Scan-2026!")
        self.activity = Activity.objects.create(
            owner_profile=self.owner,
            created_by=self.owner,
            title="Canonical scan activity",
        )
        now = timezone.now()
        self.occurrence_a = Occurrence.objects.create(
            activity=self.activity,
            label="Départ A",
            start_at=now - timedelta(minutes=30),
            end_at=now + timedelta(hours=2),
        )
        self.occurrence_b = Occurrence.objects.create(
            activity=self.activity,
            label="Départ B",
            start_at=now + timedelta(hours=3),
            end_at=now + timedelta(hours=5),
        )

    def _token(self, occurrence=None):
        access = issue_access(
            beneficiary=self.owner,
            activity=self.activity,
            occurrence=occurrence,
        )
        credential = access.credentials.get(status=CredentialStatus.ACTIVE)
        return access, render_access_credential(credential)

    def test_non_event_activity_assignment_scans_canonical_access_once(self):
        ScannerAssignment.objects.create(activity=self.activity, agent=self.agent, label="Activity-wide")
        access, token = self._token()

        first = scan_access_credential(token=token, actor=self.agent, activity=self.activity)
        second = scan_access_credential(token=token, actor=self.agent, activity=self.activity)

        self.assertEqual(first.result, AccessUseResult.ACCEPTED)
        self.assertEqual(second.result, AccessUseResult.ALREADY_USED)
        self.assertEqual(AccessUse.objects.filter(access=access, result=AccessUseResult.ACCEPTED).count(), 1)
        self.assertEqual(ScanLog.objects.count(), 0)

    def test_same_generic_scanner_cycle_is_idempotent_but_next_cycle_is_not(self):
        ScannerAssignment.objects.create(activity=self.activity, agent=self.agent, label="Activity-wide")
        access, token = self._token()

        first = scan_access_credential(
            token=token,
            actor=self.agent,
            activity=self.activity,
            client_reference="camera-cycle-1",
        )
        replay = scan_access_credential(
            token=token,
            actor=self.agent,
            activity=self.activity,
            client_reference="camera-cycle-1",
        )
        second_presentation = scan_access_credential(
            token=token,
            actor=self.agent,
            activity=self.activity,
            client_reference="camera-cycle-2",
        )

        self.assertEqual(first.result, AccessUseResult.ACCEPTED)
        self.assertEqual(replay.result, AccessUseResult.ACCEPTED)
        self.assertEqual(first.use.pk, replay.use.pk)
        self.assertEqual(second_presentation.result, AccessUseResult.ALREADY_USED)
        self.assertEqual(AccessUse.objects.filter(access=access, result=AccessUseResult.ACCEPTED).count(), 1)
        self.assertEqual(AccessUse.objects.filter(access=access).count(), 2)
        self.assertEqual(ScanLog.objects.count(), 0)

    def test_occurrence_assignment_cannot_scan_another_occurrence(self):
        ScannerAssignment.objects.create(
            activity=self.activity,
            occurrence=self.occurrence_b,
            agent=self.agent,
            label="Départ B",
        )
        access, token = self._token(self.occurrence_a)

        outcome = scan_access_credential(
            token=token,
            actor=self.agent,
            activity=self.activity,
            occurrence=self.occurrence_b,
        )

        self.assertEqual(outcome.result, AccessUseResult.WRONG_OCCURRENCE)
        self.assertFalse(AccessUse.objects.filter(access=access, result=AccessUseResult.ACCEPTED).exists())

    def test_assignment_scope_rejects_wrong_activity_and_inactive_assignment(self):
        other_activity = Activity.objects.create(
            owner_profile=self.owner,
            created_by=self.owner,
            title="Other activity",
        )
        ScannerAssignment.objects.create(activity=other_activity, agent=self.agent)
        _access, token = self._token()
        outcome = scan_access_credential(
            token=token,
            actor=self.agent,
            activity=other_activity,
        )
        self.assertEqual(outcome.result, AccessUseResult.WRONG_ACTIVITY)

        assignment = ScannerAssignment.objects.create(activity=self.activity, agent=self.other, is_active=False)
        self.assertFalse(assignment.is_current)
        with self.assertRaises(PermissionDenied):
            scan_access_credential(token=token, actor=self.other, activity=self.activity)

    def test_scan_mandate_is_minimal_and_needs_no_assignment(self):
        grant_activity_role(
            profile=self.agent,
            activity=self.activity,
            role=SystemRoleCode.ACTIVITY_SCANNER,
            granted_by=self.owner,
            source="test",
        )
        _access, token = self._token(self.occurrence_a)

        outcome = scan_access_credential(
            token=token,
            actor=self.agent,
            activity=self.activity,
            occurrence=self.occurrence_a,
        )

        self.assertEqual(outcome.result, AccessUseResult.ACCEPTED)
        self.assertTrue(can(self.agent, PermissionCode.ACTIVITY_ACCESS_SCAN, activity=self.activity))
        self.assertFalse(can(self.agent, PermissionCode.ACTIVITY_ACCESS_MANAGE, activity=self.activity))
        self.assertFalse(can(self.agent, PermissionCode.ACTIVITY_MANAGE, activity=self.activity))
        self.assertFalse(can(self.agent, PermissionCode.ACTIVITY_COMMERCE_MANAGE, activity=self.activity))
        self.assertFalse(can(self.agent, PermissionCode.FINANCE_VIEW, space=None))