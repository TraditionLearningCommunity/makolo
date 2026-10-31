from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from accounts.models import User
from authorization.constants import SystemRoleCode
from authorization.services import grant_space_role
from organizations.models import Organization, SpaceLifecycle
from funding.models import FundingContribution, FundingDetails
from funding.selectors import funding_accepts_contributions, public_fundings


class Z15FundingApiTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="z15-f-owner", email="z15-f-owner@test.local", password="x"
        )
        self.participant = User.objects.create_user(
            username="z15-f-participant",
            email="z15-f-participant@test.local",
            password="x",
        )
        self.outsider = User.objects.create_user(
            username="z15-f-outsider", email="z15-f-outsider@test.local", password="x"
        )
        self.space = Organization.objects.create(
            name="Funding Z15", slug="funding-z15", created_by=self.owner
        )
        grant_space_role(
            profile=self.owner,
            space=self.space,
            role=SystemRoleCode.SPACE_OWNER,
            granted_by=self.owner,
        )
        self.client = APIClient()

    def test_space_funding_create_manage_and_contribute_use_owner_services(self):
        self.client.force_authenticate(self.owner)
        create = self.client.post(
            "/api/v1/funding/",
            {
                "title": "Fonds Z15",
                "space_id": str(self.space.pk),
                "currency": "USD",
                "target_amount": "100.00",
                "status": "published",
                "visibility": "public",
            },
            format="json",
        )
        self.assertEqual(create.status_code, 201, create.data)
        funding_id = create.data["id"]

        listing = self.client.get(f"/api/v1/funding/?space={self.space.pk}")
        self.assertEqual(listing.status_code, 200, listing.data)
        self.assertEqual([row["id"] for row in listing.data], [funding_id])

        public = self.client.get(f"/api/v1/funding/public/{funding_id}/")
        self.assertEqual(public.status_code, 200, public.data)
        self.assertIn("contribute", public.data["capabilities"])

        self.client.force_authenticate(self.participant)
        contribution = self.client.post(
            f"/api/v1/funding/{funding_id}/contributions/",
            {"amount": "10.00", "client_reference": "z15-contribution"},
            format="json",
        )
        self.assertEqual(contribution.status_code, 201, contribution.data)
        self.assertTrue(contribution.data["payment_obligation_id"])
        lookup = self.client.get(
            f"/api/v1/funding/{funding_id}/contributions/?client_reference=z15-contribution"
        )
        self.assertEqual(lookup.status_code, 200, lookup.data)
        self.assertEqual(
            lookup.data["contribution"]["id"], contribution.data["id"]
        )
        self.assertIsNone(self.client.get(
            f"/api/v1/funding/{funding_id}/contributions/?client_reference=unknown"
        ).data["contribution"])
        obligation_id = contribution.data["payment_obligation_id"]
        detail = self.client.get(f"/api/v1/payments/obligations/{obligation_id}/")
        self.assertEqual(detail.status_code, 200, detail.data)
        self.assertIn("pay", detail.data["capabilities"])

        with override_settings(PAYMENTS_SANDBOX_ENABLED=True):
            payment = self.client.post(
                f"/api/v1/payments/obligations/{obligation_id}/",
                {
                    "provider": "sandbox",
                    "method": "card",
                    "idempotency_key": "z15-native-obligation-payment",
                },
                format="json",
            )
            self.assertEqual(payment.status_code, 201, payment.data)
            replay = self.client.post(
                f"/api/v1/payments/obligations/{obligation_id}/",
                {
                    "provider": "sandbox",
                    "method": "card",
                    "idempotency_key": "z15-native-obligation-payment",
                },
                format="json",
            )
            self.assertEqual(replay.status_code, 201, replay.data)
            self.assertEqual(payment.data["id"], replay.data["id"])
            confirmation = self.client.post(
                f"/api/v1/payments/payments/{payment.data['id']}/sandbox-complete/",
                {}, format="json",
            )
            self.assertEqual(confirmation.status_code, 200, confirmation.data)
            self.assertEqual(confirmation.data["status"], "succeeded")
            settled = self.client.get(
                f"/api/v1/payments/obligations/{obligation_id}/"
            )
            self.assertEqual(settled.status_code, 200, settled.data)
            self.assertEqual(settled.data["status"], "satisfied")
            self.assertNotIn("pay", settled.data["capabilities"])

        self.client.force_authenticate(self.outsider)
        private_lookup = self.client.get(
            f"/api/v1/funding/{funding_id}/contributions/?client_reference=z15-contribution"
        )
        self.assertEqual(private_lookup.status_code, 200, private_lookup.data)
        self.assertIsNone(private_lookup.data["contribution"])
        self.assertEqual(
            self.client.get(f"/api/v1/payments/obligations/{obligation_id}/").status_code,
            404,
        )
        self.assertEqual(
            self.client.post(
                f"/api/v1/payments/obligations/{obligation_id}/",
                {
                    "provider": "sandbox", "method": "card",
                    "idempotency_key": "z15-unauthorized",
                },
                format="json",
            ).status_code,
            404,
        )

        self.client.force_authenticate(self.outsider)
        self.assertEqual(
            self.client.get(f"/api/v1/funding/{funding_id}/").status_code,
            404,
        )


    def test_personal_funding_collection_uses_authenticated_profile_only(self):
        self.client.force_authenticate(self.participant)
        create = self.client.post(
            "/api/v1/funding/",
            {
                "title": "Projet personnel Z15",
                "currency": "USD",
                "target_amount": "75.00",
                "status": "draft",
                "visibility": "private",
            },
            format="json",
        )
        self.assertEqual(create.status_code, 201, create.data)
        funding_id = create.data["id"]

        mine = self.client.get("/api/v1/funding/")
        self.assertEqual(mine.status_code, 200, mine.data)
        self.assertEqual([row["id"] for row in mine.data], [funding_id])
        self.assertTrue(mine.data[0]["activity"]["personal"])
        self.assertIsNone(mine.data[0]["activity"]["space_id"])

        self.client.force_authenticate(self.outsider)
        foreign = self.client.get("/api/v1/funding/")
        self.assertEqual(foreign.status_code, 200, foreign.data)
        self.assertEqual(foreign.data, [])
        self.assertEqual(
            self.client.get(f"/api/v1/funding/{funding_id}/").status_code,
            404,
        )

    def test_public_discovery_and_new_contributions_follow_space_owner_visibility(self):
        """Space withdrawal must not leave a public Funding CTA or payment path."""
        self.client.force_authenticate(self.owner)
        created = self.client.post(
            "/api/v1/funding/",
            {
                "title": "Fonds sensible Z15",
                "space_id": str(self.space.pk),
                "currency": "USD",
                "target_amount": "100.00",
                "status": "published",
                "visibility": "public",
            },
            format="json",
        )
        self.assertEqual(created.status_code, 201, created.data)
        funding_id = created.data["id"]
        funding = FundingDetails.objects.select_related(
            "activity", "activity__space",
        ).get(pk=funding_id)
        public_path = f"/api/v1/funding/public/{funding_id}/"
        contribute_path = f"/api/v1/funding/{funding_id}/contributions/"
        self.client.force_authenticate(self.participant)
        self.assertEqual(self.client.get(public_path).status_code, 200)
        self.assertTrue(funding_accepts_contributions(funding))

        for field, rejected in (
            ("verification_status", "suspended"),
            ("lifecycle", SpaceLifecycle.ARCHIVED),
            ("public_profile", False),
            ("searchable", False),
        ):
            with self.subTest(field=field):
                previous = getattr(self.space, field)
                setattr(self.space, field, rejected)
                self.space.save(update_fields=[field])
                funding.activity.space.refresh_from_db()
                self.assertFalse(public_fundings().filter(pk=funding_id).exists())
                self.assertFalse(funding_accepts_contributions(funding))
                self.assertEqual(self.client.get(public_path).status_code, 404)
                refused = self.client.post(
                    contribute_path,
                    {"amount": "10.00", "client_reference": f"withdrawn-{field}"},
                    format="json",
                )
                self.assertEqual(refused.status_code, 400, refused.data)
                self.assertFalse(
                    FundingContribution.objects.filter(funding_id=funding_id).exists()
                )
                setattr(self.space, field, previous)
                self.space.save(update_fields=[field])
                funding.activity.space.refresh_from_db()
                self.assertTrue(public_fundings().filter(pk=funding_id).exists())
                self.assertTrue(funding_accepts_contributions(funding))

    def test_public_funding_excludes_inactive_personal_owner(self):
        from funding.services import create_funding
        from activities.models import ActivityStatus, ActivityVisibility

        personal = create_funding(
            actor=self.owner,
            title="Fonds personnel propriétaire",
            currency="USD",
            status=ActivityStatus.PUBLISHED,
            visibility=ActivityVisibility.PUBLIC,
        )
        self.assertTrue(public_fundings().filter(pk=personal.pk).exists())
        self.owner.is_active = False
        self.owner.save(update_fields=["is_active"])
        self.assertFalse(public_fundings().filter(pk=personal.pk).exists())
        self.assertFalse(funding_accepts_contributions(personal))
