"""L5: canonical Scanner / AccessUse for any Activity, with no Event adapter."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from access.models import AccessUse, AccessUseResult, CredentialStatus
from access.services import issue_access, render_access_credential
from activities.models import Activity, Occurrence
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role, revoke_mandate
from operations.models import CheckpointStatus, OccurrenceCheckpoint, CheckpointObservation
from scanner.models import ScannerAssignment, ScanLog


User = get_user_model()


class OccurrenceControlL5Tests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="l5-owner", email="l5-owner@example.test",
        )
        self.agent = User.objects.create_user(
            username="l5-scanner", email="l5-scanner@example.test",
        )
        self.outsider = User.objects.create_user(
            username="l5-outsider", email="l5-outsider@example.test",
        )
        self.activity = Activity.objects.create(
            owner_profile=self.owner, created_by=self.owner,
            title="Scanner hors Events",
        )
        self.occurrence = Occurrence.objects.create(
            activity=self.activity,
            start_at=timezone.now() - timedelta(minutes=5),
            end_at=timezone.now() + timedelta(hours=2),
        )
        self.mandate = grant_activity_role(
            profile=self.agent, activity=self.activity,
            role=SystemRoleCode.ACTIVITY_SCANNER, granted_by=self.owner,
        )
        self.access = issue_access(
            beneficiary=self.owner, activity=self.activity,
            occurrence=self.occurrence,
        )
        self.token = render_access_credential(
            self.access.credentials.get(status=CredentialStatus.ACTIVE),
        )
        self.context_url = (
            f"/api/v1/scanner/occurrences/{self.occurrence.pk}/context/"
        )
        self.scan_url = (
            f"/api/v1/scanner/occurrences/{self.occurrence.pk}/control/"
        )

    def test_non_event_scan_consumes_access_once_and_does_not_echo_secret(self):
        self.client.force_login(self.agent)
        context = self.client.get(self.context_url)
        self.assertEqual(context.status_code, 200)
        self.assertIn("scan", context.json()["data"]["capabilities"])
        self.assertEqual(context.json()["data"]["links"]["scan"], self.scan_url)
        first = self.client.post(
            self.scan_url,
            {"token": self.token, "client_reference": "l5-camera-1"},
        )
        self.assertEqual(first.status_code, 200)
        self.assertTrue(first.json()["accepted"])
        self.assertNotIn(self.token, first.content.decode())
        retry = self.client.post(
            self.scan_url,
            {"token": self.token, "client_reference": "l5-camera-1"},
        )
        self.assertEqual(retry.status_code, 200)
        self.assertTrue(retry.json()["accepted"])
        another = self.client.post(
            self.scan_url,
            {"token": self.token, "client_reference": "l5-camera-2"},
        )
        self.assertEqual(another.json()["result"], AccessUseResult.ALREADY_USED)
        self.assertEqual(
            AccessUse.objects.filter(
                access=self.access, result=AccessUseResult.ACCEPTED,
            ).count(), 1,
        )
        self.assertFalse(ScanLog.objects.exists())

    def test_assignment_alone_is_not_permission_and_revocation_blocks_post(self):
        self.client.force_login(self.outsider)
        ScannerAssignment.objects.create(
            activity=self.activity, occurrence=self.occurrence,
            agent=self.outsider,
        )
        self.assertEqual(self.client.get(self.context_url).status_code, 404)
        self.assertEqual(
            self.client.post(self.scan_url, {"token": self.token}).status_code,
            404,
        )
        self.client.force_login(self.agent)
        self.assertEqual(self.client.get(self.context_url).status_code, 200)
        revoke_mandate(mandate=self.mandate, actor=self.owner)
        self.assertEqual(
            self.client.post(self.scan_url, {"token": self.token}).status_code,
            404,
        )
        self.assertEqual(AccessUse.objects.count(), 0)

    def test_checkpoint_assignment_records_observation_linked_to_accessuse(self):
        cp = OccurrenceCheckpoint.objects.create(
            occurrence=self.occurrence, key="accueil", label="Accueil",
            required=True, status=CheckpointStatus.OPEN,
        )
        ScannerAssignment.objects.create(
            activity=self.activity, occurrence=self.occurrence,
            checkpoint=cp, agent=self.agent,
        )
        self.client.force_login(self.agent)
        response = self.client.post(
            self.scan_url,
            {"token": self.token, "client_reference": "l5-cp-1"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["accepted"])
        self.assertTrue(response.json()["checkpoint_observed"])
        observation = CheckpointObservation.objects.get(checkpoint=cp)
        self.assertEqual(observation.access_use.access_id, self.access.pk)

    def test_invalid_code_never_returns_credential_data(self):
        self.client.force_login(self.agent)
        response = self.client.post(
            self.scan_url, {"token": "invalid-secret"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertNotIn("invalid-secret", response.content.decode())
