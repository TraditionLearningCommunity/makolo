from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from activities.models import Activity, ActivityStatus, Occurrence, OccurrenceStatus
from journeys.models import Journey, JourneyStatus, WorkflowKind
from organizations.models import Organization
from personal_assets.models import PersonalAsset
from trust.credential_models import Credential, CredentialStatus, CredentialType
from sharing.models import ShareEnvelope
from trust.models import Proof, ProofStatus, ProofType


User = get_user_model()


class PersonalTrustResourcesCheckpoint2Tests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="trust-resource-owner",
            email="trust-resource-owner@example.test",
        )
        self.participant = User.objects.create_user(
            username="trust-resource-participant",
            email="trust-resource-participant@example.test",
        )
        self.other = User.objects.create_user(
            username="trust-resource-other",
            email="trust-resource-other@example.test",
        )
        self.space = Organization.objects.create(
            name="Institut Makolo",
            created_by=self.owner,
            public_profile=True,
        )
        self.activity = Activity.objects.create(
            space=self.space,
            created_by=self.owner,
            title="Formation pratique",
            status=ActivityStatus.PUBLISHED,
        )
        now = timezone.now()
        self.occurrence = Occurrence.objects.create(
            activity=self.activity,
            label="Session finale",
            start_at=now,
            end_at=now,
            status=OccurrenceStatus.COMPLETED,
        )
        self.journey = Journey.objects.create(
            initiated_by=self.participant,
            beneficiary=self.participant,
            activity=self.activity,
            occurrence=self.occurrence,
            workflow=WorkflowKind.REGISTRATION,
            status=JourneyStatus.FULFILLED,
            fulfilled_at=now,
        )
        self.proof = Proof.objects.create(
            subject_profile=self.participant,
            journey=self.journey,
            occurrence=self.occurrence,
            proof_type=ProofType.JOURNEY_COMPLETED,
            status=ProofStatus.ACTIVE,
            is_public=True,
            issued_by=self.owner,
        )
        self.revoked_proof = Proof.objects.create(
            subject_profile=self.participant,
            journey=self.journey,
            occurrence=self.occurrence,
            proof_type=ProofType.SERVICE_COMPLETED,
            status=ProofStatus.REVOKED,
            is_public=False,
            issued_by=self.owner,
            revoked_by=self.owner,
            revoked_at=now,
            revoke_reason="Correction du fait établi",
        )
        self.credential = Credential(
            subject_profile=self.participant,
            issuer_space=self.space,
            issued_by=self.owner,
            activity=self.activity,
            occurrence=self.occurrence,
            journey=self.journey,
            credential_type=CredentialType.COMPLETION,
            title="Certificat Makolo",
            statement="Formation terminée.",
            status=CredentialStatus.ISSUED,
        )
        self.credential.full_clean()
        self.credential.save()
        self.revoked_credential = Credential(
            subject_profile=self.participant,
            issuer_space=self.space,
            issued_by=self.owner,
            activity=self.activity,
            occurrence=self.occurrence,
            journey=self.journey,
            credential_type=CredentialType.ATTESTATION,
            title="Attestation historique",
            status=CredentialStatus.REVOKED,
            revoked_by=self.owner,
            revoked_at=now,
            revoke_reason="Titre remplacé",
        )
        self.revoked_credential.full_clean()
        self.revoked_credential.save()
        self.asset = PersonalAsset.objects.create(
            controller=self.participant,
            subject_profile=self.participant,
            title="CV Makolo",
        )
        self.client.force_login(self.participant)

    def test_moi_preview_handoffs_open_canonical_resource_depths(self):
        response = self.client.get(reverse("core:participant-me"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            reverse("personal_assets:detail", args=[self.asset.pk]),
        )
        self.assertContains(
            response,
            reverse("trust:proof-detail", args=[self.proof.pk]),
        )
        self.assertContains(
            response,
            reverse("trust:credential-detail", args=[self.credential.pk]),
        )
        self.assertContains(response, "Titres")

    def test_private_resource_pages_are_no_store_but_public_verification_stays_public(self):
        for url in (
            reverse("trust:my-proofs"),
            reverse("trust:proof-detail", args=[self.proof.pk]),
            reverse("trust:my-credentials"),
            reverse("trust:credential-detail", args=[self.credential.pk]),
        ):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    response["Cache-Control"],
                    "private, no-store",
                )

        proof_verify = self.client.get(
            reverse("trust:proof-verify", args=[self.proof.public_id])
        )
        self.assertEqual(proof_verify.status_code, 200)
        self.assertNotEqual(
            proof_verify.headers.get("Cache-Control"),
            "private, no-store",
        )

    def test_hub_links_to_distinct_proof_and_title_surfaces(self):
        response = self.client.get(reverse("personal_assets:list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("trust:my-proofs"))
        self.assertContains(response, reverse("trust:my-credentials"))
        self.assertContains(response, "Mes preuves")
        self.assertContains(response, "Mes titres")

        projection = self.client.get(
            reverse("personal-projections:resources"),
        )
        self.assertEqual(projection.status_code, 200)
        data = projection.json()["data"]
        self.assertEqual(
            data["proofs"]["links"]["collection"],
            reverse("personal-projections:proofs"),
        )
        self.assertEqual(
            data["credentials"]["links"]["collection"],
            reverse("personal-projections:titles"),
        )

    def test_proof_collection_filters_searches_and_exposes_only_public_verify(self):
        response = self.client.get(
            reverse("personal-projections:proofs"),
            {"q": "Formation", "status": "active", "sort": "recent"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["items"][0]["id"], str(self.proof.pk))
        self.assertIn("verify", data["items"][0]["links"])
        self.assertEqual(
            data["items"][0]["links"]["passport"],
            reverse("personal-projections:passport"),
        )

        revoked = self.client.get(
            reverse("personal-projections:proofs"),
            {"status": "revoked"},
        ).json()["data"]
        self.assertEqual(revoked["count"], 1)
        self.assertNotIn("verify", revoked["items"][0]["links"])
        self.assertNotIn("passport", revoked["items"][0]["links"])

    def test_proof_detail_is_private_and_preserves_revocation_reason(self):
        response = self.client.get(
            reverse(
                "personal-projections:proof-detail",
                kwargs={"pk": self.revoked_proof.pk},
            )
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["status"], ProofStatus.REVOKED)
        self.assertEqual(
            data["revocation"]["reason"],
            "Correction du fait établi",
        )

        self.client.force_login(self.other)
        denied = self.client.get(
            reverse(
                "personal-projections:proof-detail",
                kwargs={"pk": self.proof.pk},
            )
        )
        self.assertEqual(denied.status_code, 404)

    def test_title_collection_searches_filters_and_exposes_issuer(self):
        response = self.client.get(
            reverse("personal-projections:titles"),
            {
                "q": "Institut",
                "status": "issued",
                "type": CredentialType.COMPLETION,
                "sort": "title",
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["count"], 1)
        item = data["items"][0]
        self.assertEqual(item["title"], "Certificat Makolo")
        self.assertEqual(item["issuer"]["name"], "Institut Makolo")
        self.assertIn("verify", item["links"])
        self.assertEqual(
            item["links"]["passport"],
            reverse("personal-projections:passport"),
        )

    def test_title_detail_is_private_and_keeps_statement_and_revocation(self):
        response = self.client.get(
            reverse(
                "personal-projections:title-detail",
                kwargs={"pk": self.credential.pk},
            )
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["statement"], "Formation terminée.")
        self.assertEqual(data["beneficiary"]["id"], str(self.participant.pk))

        revoked = self.client.get(
            reverse(
                "personal-projections:title-detail",
                kwargs={"pk": self.revoked_credential.pk},
            )
        ).json()["data"]
        self.assertEqual(revoked["status"], CredentialStatus.REVOKED)
        self.assertEqual(revoked["revocation"]["reason"], "Titre remplacé")

        self.client.force_login(self.other)
        denied = self.client.get(
            reverse(
                "personal-projections:title-detail",
                kwargs={"pk": self.credential.pk},
            )
        )
        self.assertEqual(denied.status_code, 404)

    def test_web_collections_and_details_remain_owner_scoped(self):
        proofs = self.client.get(reverse("trust:my-proofs"))
        self.assertEqual(proofs.status_code, 200)
        self.assertContains(proofs, "Mes preuves")
        self.assertContains(proofs, "Formation pratique")
        self.assertContains(proofs, reverse("trust:proof-detail", args=[self.proof.pk]))

        titles = self.client.get(reverse("trust:my-credentials"))
        self.assertEqual(titles.status_code, 200)
        self.assertContains(titles, "Mes titres")
        self.assertContains(titles, "Certificat Makolo")
        self.assertContains(
            titles,
            reverse("trust:credential-detail", args=[self.credential.pk]),
        )

        self.client.force_login(self.other)
        proof_detail = self.client.get(
            reverse("trust:proof-detail", args=[self.proof.pk])
        )
        title_detail = self.client.get(
            reverse("trust:credential-detail", args=[self.credential.pk])
        )
        self.assertEqual(proof_detail.status_code, 404)
        self.assertEqual(title_detail.status_code, 404)

    def test_trust_details_preserve_only_owner_collection_return_context(self):
        proof_detail = reverse("trust:proof-detail", args=[self.proof.pk])
        proof_return = reverse("trust:my-proofs") + "?status=active&q=Formation"
        response = self.client.get(proof_detail, {"return": proof_return})
        self.assertEqual(response.context["return_url"], proof_return)

        title_detail = reverse(
            "trust:credential-detail",
            args=[self.credential.pk],
        )
        title_return = (
            reverse("trust:my-credentials") + "?status=issued&sort=title"
        )
        response = self.client.get(title_detail, {"return": title_return})
        self.assertEqual(response.context["return_url"], title_return)

        rejected = self.client.get(
            proof_detail,
            {"return": "https://evil.example/trust/proofs/?q=private"},
        )
        self.assertEqual(
            rejected.context["return_url"],
            reverse("trust:my-proofs"),
        )

    def test_resource_details_only_offer_public_representation_sharing(self):
        before = ShareEnvelope.objects.count()

        proof = self.client.get(
            reverse("trust:proof-detail", args=[self.proof.pk])
        )
        self.assertEqual(proof.status_code, 200)
        self.assertContains(proof, "data-makolo-share")
        self.assertContains(
            proof,
            reverse("trust:proof-verify", args=[self.proof.public_id]),
        )
        self.assertContains(proof, "Ouvrir mon Passeport")

        private_proof = self.client.get(
            reverse("trust:proof-detail", args=[self.revoked_proof.pk])
        )
        self.assertEqual(private_proof.status_code, 200)
        self.assertNotContains(private_proof, "data-makolo-share")
        self.assertNotContains(private_proof, "Ouvrir mon Passeport")

        credential = self.client.get(
            reverse("trust:credential-detail", args=[self.credential.pk])
        )
        self.assertEqual(credential.status_code, 200)
        self.assertContains(credential, "data-makolo-share")
        self.assertContains(
            credential,
            reverse(
                "trust:credential-verify",
                args=[self.credential.public_id],
            ),
        )
        self.assertContains(credential, "Ouvrir mon Passeport")

        self.assertEqual(ShareEnvelope.objects.count(), before)

    def test_public_verification_surfaces_show_revocation_without_private_reason(self):
        proof_verify = self.client.get(
            reverse("trust:proof-verify", args=[self.proof.public_id])
        )
        self.assertEqual(proof_verify.status_code, 200)
        self.assertContains(proof_verify, "Preuve valide")

        credential_verify = self.client.get(
            reverse(
                "trust:credential-verify",
                args=[self.revoked_credential.public_id],
            )
        )
        self.assertEqual(credential_verify.status_code, 200)
        self.assertContains(credential_verify, "Titre révoqué")
        self.assertNotContains(credential_verify, "Titre remplacé")
