from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserProfile
from activities.models import Activity, ActivityStatus, ActivityVisibility
from authorization.constants import SystemRoleCode
from authorization.services import grant_space_role
from journeys.models import Journey, JourneyStatus, WorkflowKind
from organizations.models import Organization
from topics.models import ActivityTopic, ProfileInterest, Topic
from trust.credential_models import Credential, CredentialStatus, CredentialType
from trust.models import Proof, ProofStatus, ProofType


User = get_user_model()
PASSWORD = "Strong-G6-Password-2026!"


class G6PassportFixtureMixin:
    def build_fixture(self):
        self.amina = User.objects.create_user(
            username="g6-amina",
            email="amina.g6@example.test",
            password=PASSWORD,
            first_name="Amina",
            last_name="B.",
            bio="Bio publique Amina",
            phone="+243999111222",
            website="https://amina.example.test",
        )
        self.amina_profile = UserProfile.objects.create(
            user=self.amina,
            city="Lubumbashi",
            country="RDC",
            address="Adresse privée G6",
            latitude=-11.66,
            longitude=27.48,
            public_profile=True,
            searchable=False,
        )
        self.patrick = User.objects.create_user(
            username="g6-patrick",
            email="patrick.g6@example.test",
            password=PASSWORD,
        )
        UserProfile.objects.create(user=self.patrick, public_profile=True)
        self.space_owner = User.objects.create_user(
            username="g6-space-owner",
            email="owner.g6@example.test",
            password=PASSWORD,
        )
        UserProfile.objects.create(user=self.space_owner, public_profile=False)
        self.outsider = User.objects.create_user(
            username="g6-outsider",
            email="outsider.g6@example.test",
            password=PASSWORD,
        )
        UserProfile.objects.create(user=self.outsider, public_profile=False)

        self.tech = Topic.objects.create(code="g6-tech", label="Technologie")
        self.health = Topic.objects.create(code="g6-health", label="Santé")
        ProfileInterest.objects.create(profile=self.amina, topic=self.tech, is_public=True)
        ProfileInterest.objects.create(profile=self.amina, topic=self.health, is_public=False)

        self.owned_public = Activity.objects.create(
            owner_profile=self.amina,
            created_by=self.amina,
            title="Atelier Python G6",
            status=ActivityStatus.PUBLISHED,
            visibility=ActivityVisibility.PUBLIC,
        )
        self.owned_private = Activity.objects.create(
            owner_profile=self.amina,
            created_by=self.amina,
            title="Atelier santé privé G6",
            status=ActivityStatus.PUBLISHED,
            visibility=ActivityVisibility.PRIVATE,
        )
        ActivityTopic.objects.create(activity=self.owned_public, topic=self.tech)
        ActivityTopic.objects.create(activity=self.owned_private, topic=self.health)

        self.space = Organization.objects.create(
            name="Tech Hub Lubumbashi G6",
            slug="tech-hub-lubumbashi-g6",
            description="Espace public G6",
            website="https://hub.example.test",
            contact_email="secret-hub@example.test",
            contact_phone="+243888000111",
            city="Lubumbashi",
            country="RDC",
            public_profile=True,
            created_by=self.space_owner,
        )
        grant_space_role(
            profile=self.space_owner,
            space=self.space,
            role=SystemRoleCode.SPACE_OWNER,
            source="g6-passport-test",
        )
        self.space_public_activity = Activity.objects.create(
            space=self.space,
            created_by=self.space_owner,
            title="Conférence IA Lubumbashi 2026",
            status=ActivityStatus.PUBLISHED,
            visibility=ActivityVisibility.PUBLIC,
        )
        self.space_private_activity = Activity.objects.create(
            space=self.space,
            created_by=self.space_owner,
            title="Réunion interne privée G6",
            status=ActivityStatus.PUBLISHED,
            visibility=ActivityVisibility.PRIVATE,
        )
        ActivityTopic.objects.create(activity=self.space_public_activity, topic=self.tech)
        ActivityTopic.objects.create(activity=self.space_private_activity, topic=self.health)

        self.journey = Journey.objects.create(
            initiated_by=self.amina,
            beneficiary=self.amina,
            activity=self.space_public_activity,
            workflow=WorkflowKind.REGISTRATION,
            status=JourneyStatus.FULFILLED,
            fulfilled_at=timezone.now(),
        )
        self.public_proof = Proof.objects.create(
            subject_profile=self.amina,
            journey=self.journey,
            proof_type=ProofType.PARTICIPATION_CONFIRMED,
            status=ProofStatus.ACTIVE,
            is_public=True,
            issued_by=self.space_owner,
        )
        self.private_proof = Proof.objects.create(
            subject_profile=self.amina,
            journey=self.journey,
            proof_type=ProofType.JOURNEY_COMPLETED,
            status=ProofStatus.ACTIVE,
            is_public=False,
            issued_by=self.space_owner,
        )
        self.valid_credential = Credential.objects.create(
            subject_profile=self.amina,
            issuer_space=self.space,
            issued_by=self.space_owner,
            activity=self.space_public_activity,
            journey=self.journey,
            credential_type=CredentialType.PARTICIPATION,
            title="Attestation participation G6",
        )
        self.revoked_credential = Credential.objects.create(
            subject_profile=self.amina,
            issuer_space=self.space,
            issued_by=self.space_owner,
            activity=self.space_public_activity,
            credential_type=CredentialType.ATTESTATION,
            title="Ancienne attestation révoquée G6",
            status=CredentialStatus.REVOKED,
            revoked_by=self.space_owner,
            revoked_at=timezone.now(),
            revoke_reason="Corrigée",
        )
        self.patrick_credential = Credential.objects.create(
            subject_profile=self.patrick,
            issuer_space=self.space,
            issued_by=self.space_owner,
            activity=self.space_public_activity,
            credential_type=CredentialType.ATTESTATION,
            title="Credential privé de Patrick G6",
        )


class G6ProfilePassportTests(G6PassportFixtureMixin, TestCase):
    def setUp(self):
        self.build_fixture()
        self.public_url = reverse("sharing:passport-profile", kwargs={"profile_id": self.amina.pk})

    def test_public_profile_passport_exposes_only_public_authorized_facts(self):
        response = self.client.get(self.public_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Bio publique Amina")
        self.assertContains(response, "Technologie")
        self.assertContains(response, "Atelier Python G6")
        self.assertContains(response, "Participation confirmée")
        self.assertContains(response, "Attestation participation G6")
        self.assertContains(response, "Délivrée par Tech Hub Lubumbashi G6")
        self.assertNotContains(response, "Santé")
        self.assertNotContains(response, "Atelier santé privé G6")
        self.assertNotContains(response, "Journey accomplie")
        self.assertNotContains(response, "Ancienne attestation révoquée G6")
        for private_value in (
            self.amina.email,
            self.amina.phone,
            "Adresse privée G6",
            "-11.66",
            "27.48",
        ):
            self.assertNotContains(response, private_value)

    def test_private_profile_is_not_public_but_owner_can_open_complete_passport(self):
        self.amina_profile.public_profile = False
        self.amina_profile.save(update_fields=["public_profile", "updated_at"])
        self.assertEqual(self.client.get(self.public_url).status_code, 404)
        self.client.force_login(self.amina)
        response = self.client.get(reverse("sharing:passport-me"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Complet")
        self.assertContains(response, "Santé")
        self.assertContains(response, "Atelier santé privé G6")

    def test_complete_variant_is_reserved_to_profile_owner(self):
        self.client.force_login(self.outsider)
        denied = self.client.get(self.public_url, {"variant": "complete"})
        self.assertEqual(denied.status_code, 403)
        self.client.force_login(self.amina)
        allowed = self.client.get(self.public_url, {"variant": "complete"})
        self.assertEqual(allowed.status_code, 200)
        self.assertContains(allowed, "Atelier santé privé G6")

    def test_revoked_credential_is_not_presented_as_valid_and_trust_remains_authority(self):
        public_response = self.client.get(self.public_url)
        self.assertNotContains(public_response, self.revoked_credential.title)
        verify_url = reverse(
            "trust:credential-verify",
            kwargs={"public_id": self.revoked_credential.public_id},
        )
        verification = self.client.get(verify_url)
        self.assertContains(verification, "Révoquée", status_code=200)

        self.client.force_login(self.amina)
        complete = self.client.get(self.public_url, {"variant": "complete"})
        self.assertContains(complete, self.revoked_credential.title)
        self.assertContains(complete, "Révoquée")

    def test_custom_selection_rejects_foreign_credential_idor(self):
        self.client.force_login(self.amina)
        response = self.client.get(
            reverse("sharing:passport-me"),
            {
                "variant": "custom",
                "credential": str(self.patrick_credential.pk),
                "include": "bio",
            },
        )
        self.assertEqual(response.status_code, 403)

    def test_thematic_variant_uses_only_real_topic_links(self):
        self.client.force_login(self.amina)
        response = self.client.get(
            reverse("sharing:passport-me"),
            {"variant": "thematic", "topic": self.tech.code},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Technologie")
        self.assertContains(response, "Atelier Python G6")
        self.assertContains(response, "Attestation participation G6")
        self.assertNotContains(response, "Atelier santé privé G6")

    def test_custom_selection_includes_only_server_validated_items(self):
        self.client.force_login(self.amina)
        response = self.client.get(
            reverse("sharing:passport-me"),
            {
                "variant": "custom",
                "include": ["bio", "interests"],
                "activity": str(self.owned_public.pk),
                "proof": str(self.public_proof.pk),
                "credential": str(self.valid_credential.pk),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Bio publique Amina")
        self.assertContains(response, "Atelier Python G6")
        self.assertContains(response, "Participation confirmée")
        self.assertContains(response, "Attestation participation G6")
        self.assertNotContains(response, "Atelier santé privé G6")

    def test_print_ready_and_downloadable_html_export(self):
        response = self.client.get(self.public_url, {"download": "1"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/html; charset=utf-8")
        self.assertIn("attachment;", response["Content-Disposition"])
        self.assertContains(response, 'data-passport-print-ready="true"')
        self.assertContains(response, "Imprimer / Enregistrer en PDF")


class G6SpacePassportTests(G6PassportFixtureMixin, TestCase):
    def setUp(self):
        self.build_fixture()
        self.url = reverse("sharing:passport-space", kwargs={"slug": self.space.slug})

    def test_public_space_passport_uses_only_public_activities_and_never_lists_beneficiaries(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Conférence IA Lubumbashi 2026")
        self.assertNotContains(response, "Réunion interne privée G6")
        self.assertContains(response, "Attestation de participation")
        self.assertNotContains(response, self.amina.username)
        self.assertNotContains(response, self.amina.email)
        self.assertNotContains(response, self.space.contact_email)
        self.assertNotContains(response, self.space.contact_phone)

    def test_space_complete_requires_workspace_authority(self):
        self.client.force_login(self.outsider)
        denied = self.client.get(self.url, {"variant": "complete"})
        self.assertEqual(denied.status_code, 403)

        self.client.force_login(self.space_owner)
        allowed = self.client.get(self.url, {"variant": "complete"})
        self.assertEqual(allowed.status_code, 200)
        self.assertContains(allowed, "Réunion interne privée G6")

    def test_non_public_space_is_hidden_from_anonymous_users(self):
        self.space.public_profile = False
        self.space.save(update_fields=["public_profile", "updated_at"])
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.client.force_login(self.space_owner)
        self.assertEqual(self.client.get(self.url, {"variant": "complete"}).status_code, 200)
