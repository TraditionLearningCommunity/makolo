import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from access.models import Access, AccessStatus, AccessUse, AccessUseResult
from activities.models import Activity, ActivityStatus, Occurrence, OccurrenceStatus
from activities.services import create_activity
from authorization.constants import SystemRoleCode
from authorization.services import (
    ensure_platform_admin_mandate,
    grant_activity_role,
    grant_space_role,
    revoke_mandate,
)
from journeys.models import Journey, JourneyStatus, WorkflowKind
from organizations.models import Organization

from .credential_models import CredentialStatus, CredentialType
from .credential_selectors import credentials_for_profile, public_credential_by_id
from .credential_services import issue_credential, revoke_credential
from .models import ProofType
from .selectors import public_proof_by_id
from .services import issue_proof


User = get_user_model()


class CredentialFixtureMixin:
    def build_fixture(self):
        self.owner = User.objects.create_user(
            username="g5-owner",
            email="g5-owner@example.test",
            password="StrongPass2026!",
        )
        self.participant = User.objects.create_user(
            username="g5-participant",
            email="g5-participant@example.test",
            password="StrongPass2026!",
        )
        self.outsider = User.objects.create_user(
            username="g5-outsider",
            email="g5-outsider@example.test",
            password="StrongPass2026!",
        )
        self.staff = User.objects.create_user(
            username="g5-staff",
            email="g5-staff@example.test",
            password="StrongPass2026!",
            is_staff=True,
        )
        self.space = Organization.objects.create(
            name="G5 Credentials Space",
            created_by=self.owner,
            public_profile=True,
        )
        grant_space_role(
            profile=self.owner,
            space=self.space,
            role=SystemRoleCode.SPACE_OWNER,
            source="g5-credentials-test",
        )
        ensure_platform_admin_mandate(profile=self.staff, source="g5-credentials-test")
        self.activity = Activity.objects.create(
            space=self.space,
            created_by=self.owner,
            title="G5 Formation",
            status=ActivityStatus.PUBLISHED,
        )
        now = timezone.now()
        self.occurrence = Occurrence.objects.create(
            activity=self.activity,
            label="Session G5",
            start_at=now - timedelta(hours=2),
            end_at=now - timedelta(hours=1),
            status=OccurrenceStatus.COMPLETED,
        )
        self.journey = Journey.objects.create(
            initiated_by=self.participant,
            beneficiary=self.participant,
            activity=self.activity,
            occurrence=self.occurrence,
            workflow=WorkflowKind.REGISTRATION,
            status=JourneyStatus.FULFILLED,
            fulfilled_at=now - timedelta(minutes=50),
        )


class CredentialIssuanceTests(CredentialFixtureMixin, TestCase):
    def setUp(self):
        self.build_fixture()

    def test_space_authority_issues_completion_with_canonical_issuer_beneficiary_and_source(self):
        credential = issue_credential(
            activity=self.activity,
            subject_profile=self.participant,
            journey=self.journey,
            credential_type=CredentialType.COMPLETION,
            actor=self.owner,
            title="Certificat G5",
            statement="Formation terminée avec succès.",
        )

        self.assertEqual(credential.issuer_space_id, self.space.pk)
        self.assertIsNone(credential.issuer_profile_id)
        self.assertEqual(credential.subject_profile_id, self.participant.pk)
        self.assertEqual(credential.activity_id, self.activity.pk)
        self.assertEqual(credential.occurrence_id, self.occurrence.pk)
        self.assertEqual(credential.journey_id, self.journey.pk)
        self.assertEqual(credential.status, CredentialStatus.ISSUED)
        self.assertEqual(credential.issued_by_id, self.owner.pk)

    def test_unauthorized_actor_is_refused_and_mandate_is_rechecked(self):
        with self.assertRaises(PermissionDenied):
            issue_credential(
                activity=self.activity,
                subject_profile=self.participant,
                journey=self.journey,
                credential_type=CredentialType.COMPLETION,
                actor=self.outsider,
            )

        mandate = grant_activity_role(
            profile=self.outsider,
            activity=self.activity,
            role=SystemRoleCode.ACTIVITY_LOCAL_MANAGER,
            granted_by=self.owner,
            source="g5-credentials-test",
        )
        first = issue_credential(
            activity=self.activity,
            subject_profile=self.participant,
            credential_type=CredentialType.ATTESTATION,
            actor=self.outsider,
            title="Validation explicite 1",
        )
        self.assertEqual(first.issued_by_id, self.outsider.pk)

        revoke_mandate(mandate=mandate, actor=self.owner)
        with self.assertRaises(PermissionDenied):
            issue_credential(
                activity=self.activity,
                subject_profile=self.participant,
                credential_type=CredentialType.ATTESTATION,
                actor=self.outsider,
                title="Validation explicite 2",
            )

    def test_access_existence_alone_never_issues_participation(self):
        access = Access.objects.create(
            beneficiary=self.participant,
            activity=self.activity,
            occurrence=self.occurrence,
            journey=self.journey,
            issued_by=self.owner,
            status=AccessStatus.VALID,
        )
        with self.assertRaises(ValidationError):
            issue_credential(
                activity=self.activity,
                subject_profile=self.participant,
                journey=self.journey,
                credential_type=CredentialType.PARTICIPATION,
                actor=self.owner,
            )

        AccessUse.objects.create(
            access=access,
            actor=self.owner,
            occurrence=self.occurrence,
            result=AccessUseResult.ACCEPTED,
            source="g5-test",
        )
        credential = issue_credential(
            activity=self.activity,
            subject_profile=self.participant,
            journey=self.journey,
            credential_type=CredentialType.PARTICIPATION,
            actor=self.owner,
        )
        self.assertEqual(credential.status, CredentialStatus.ISSUED)

    def test_personal_activity_uses_profile_issuer_without_fake_space(self):
        personal_owner = User.objects.create_user(
            username="g5-personal-owner",
            email="g5-personal@example.test",
            password="StrongPass2026!",
        )
        personal_activity = create_activity(
            created_by=personal_owner,
            owner_profile=personal_owner,
            title="G5 Personal Activity",
            status=ActivityStatus.PUBLISHED,
        )
        personal_journey = Journey.objects.create(
            initiated_by=self.participant,
            beneficiary=self.participant,
            activity=personal_activity,
            workflow=WorkflowKind.REGISTRATION,
            status=JourneyStatus.FULFILLED,
            fulfilled_at=timezone.now(),
        )
        credential = issue_credential(
            activity=personal_activity,
            subject_profile=self.participant,
            journey=personal_journey,
            credential_type=CredentialType.COMPLETION,
            actor=personal_owner,
        )
        self.assertIsNone(credential.issuer_space_id)
        self.assertEqual(credential.issuer_profile_id, personal_owner.pk)
        self.assertIsNone(personal_activity.space_id)


class CredentialLifecycleTests(CredentialFixtureMixin, TestCase):
    def setUp(self):
        self.build_fixture()
        self.credential = issue_credential(
            activity=self.activity,
            subject_profile=self.participant,
            journey=self.journey,
            credential_type=CredentialType.COMPLETION,
            actor=self.owner,
            title="G5 Immutable Credential",
        )

    def test_issued_contract_is_immutable_and_cannot_be_deleted(self):
        self.credential.title = "Réécriture silencieuse"
        with self.assertRaises(ValidationError):
            self.credential.save()
        self.credential.refresh_from_db()

        self.credential.status = CredentialStatus.REVOKED
        self.credential.revoked_at = timezone.now()
        with self.assertRaises(ValidationError):
            self.credential.save()
        self.credential.refresh_from_db()

        with self.assertRaises(ValidationError):
            self.credential.delete()

    def test_controlled_revocation_preserves_actor_time_reason_and_public_history(self):
        revoked = revoke_credential(
            credential=self.credential,
            actor=self.owner,
            reason="Résultat corrigé par l’émetteur",
        )
        self.assertEqual(revoked.status, CredentialStatus.REVOKED)
        self.assertEqual(revoked.revoked_by_id, self.owner.pk)
        self.assertIsNotNone(revoked.revoked_at)
        self.assertEqual(revoked.revoke_reason, "Résultat corrigé par l’émetteur")

        visible = public_credential_by_id(revoked.public_id)
        self.assertEqual(visible.status, CredentialStatus.REVOKED)
        self.assertEqual(visible.verification_state, "revoked")

        revoked.revoke_reason = "Réécriture"
        with self.assertRaises(ValidationError):
            revoked.save()

    def test_public_web_and_api_distinguish_valid_revoked_and_unknown(self):
        web_url = reverse("trust:credential-verify", kwargs={"public_id": self.credential.public_id})
        response = self.client.get(web_url)
        self.assertContains(response, "Valide", status_code=200)
        self.assertContains(response, self.participant.username)
        self.assertContains(response, self.space.name)

        api_url = reverse("trust_api:credential-verify", kwargs={"public_id": self.credential.public_id})
        response = self.client.get(api_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["verification_state"], "valid")

        revoke_credential(credential=self.credential, actor=self.owner, reason="withdrawn")
        response = self.client.get(api_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["verification_state"], "revoked")

        unknown = reverse("trust_api:credential-verify", kwargs={"public_id": uuid.uuid4()})
        self.assertEqual(self.client.get(unknown).status_code, 404)

    def test_g6_selector_can_request_only_valid_credentials_without_passport_projection(self):
        second = issue_credential(
            activity=self.activity,
            subject_profile=self.participant,
            credential_type=CredentialType.ATTESTATION,
            actor=self.owner,
            title="G5 Other Attestation",
        )
        revoke_credential(credential=self.credential, actor=self.owner, reason="superseded")

        all_credentials = list(credentials_for_profile(self.participant))
        valid_credentials = list(credentials_for_profile(self.participant, valid_only=True))
        self.assertEqual({item.pk for item in all_credentials}, {self.credential.pk, second.pk})
        self.assertEqual([item.pk for item in valid_credentials], [second.pk])


class CredentialCompatibilityTests(CredentialFixtureMixin, TestCase):
    def setUp(self):
        self.build_fixture()

    def test_existing_proof_contract_remains_independent_and_publicly_verifiable(self):
        proof = issue_proof(
            journey=self.journey,
            proof_type=ProofType.JOURNEY_COMPLETED,
            actor=self.staff,
            is_public=True,
        )
        credential = issue_credential(
            activity=self.activity,
            subject_profile=self.participant,
            journey=self.journey,
            credential_type=CredentialType.COMPLETION,
            actor=self.owner,
        )

        self.assertIsNotNone(public_proof_by_id(proof.public_id))
        self.assertIsNotNone(public_credential_by_id(credential.public_id))
        self.assertNotEqual(proof.pk, credential.pk)
        self.assertEqual(proof.subject_profile_id, credential.subject_profile_id)

    def test_issue_api_reuses_server_policy_and_returns_relational_contract(self):
        self.client.force_login(self.owner)
        url = reverse("trust_api:credential-issue", kwargs={"activity_id": self.activity.pk})
        response = self.client.post(
            url,
            data={
                "subject_profile_id": str(self.participant.pk),
                "journey_id": str(self.journey.pk),
                "credential_type": CredentialType.COMPLETION,
                "title": "G5 API Certificate",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["beneficiary"]["id"], str(self.participant.pk))
        self.assertEqual(payload["issuer"]["id"], str(self.space.pk))
        self.assertEqual(payload["source"]["activity"]["id"], str(self.activity.pk))
        self.assertEqual(payload["source"]["journey_id"], str(self.journey.pk))

        self.client.force_login(self.outsider)
        denied = self.client.post(
            url,
            data={
                "subject_profile_id": str(self.participant.pk),
                "journey_id": str(self.journey.pk),
                "credential_type": CredentialType.COMPLETION,
                "title": "Unauthorized",
            },
            content_type="application/json",
        )
        self.assertEqual(denied.status_code, 403)
