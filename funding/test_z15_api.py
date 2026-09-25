from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import User
from authorization.constants import SystemRoleCode
from authorization.services import grant_space_role
from organizations.models import Organization


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

        self.client.force_authenticate(self.participant)
        contribution = self.client.post(
            f"/api/v1/funding/{funding_id}/contributions/",
            {"amount": "10.00", "client_reference": "z15-contribution"},
            format="json",
        )
        self.assertEqual(contribution.status_code, 201, contribution.data)
        self.assertTrue(contribution.data["payment_obligation_id"])

        self.client.force_authenticate(self.outsider)
        self.assertEqual(
            self.client.get(f"/api/v1/funding/{funding_id}/").status_code,
            404,
        )
