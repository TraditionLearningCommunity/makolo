from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from activities.models import Activity
from organizations.models import Organization, SpaceArchetype, SpaceLifecycle


class PublicSpaceApiTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(
            username="public-space-owner",
            email="public-space-owner@example.test",
            password="Test-pass-2026!",
        )
        self.visible = Organization.objects.create(
            name="Visible Association",
            description="Projet collectif public.",
            city="Lubumbashi",
            country="RDC",
            created_by=self.owner,
        )
        self.private = Organization.objects.create(
            name="Private Association",
            public_profile=False,
            created_by=self.owner,
        )
        self.hidden = Organization.objects.create(
            name="Hidden Association",
            searchable=False,
            created_by=self.owner,
        )
        self.inactive = Organization.objects.create(
            name="Inactive Association",
            lifecycle=SpaceLifecycle.ARCHIVED,
            created_by=self.owner,
        )

    def test_anonymous_directory_filters_hidden_spaces_and_discloses_minimum(self):
        response = self.client.get("/api/v1/organizations/public-spaces/")
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["results"][0]["slug"], self.visible.slug)
        self.assertNotIn("created_by", data["results"][0])
        self.assertNotIn("contact_email", data["results"][0])
        self.assertNotIn("contact_phone", data["results"][0])
        self.assertNotIn("verification_status", data["results"][0])
        self.assertNotIn("permissions", data["results"][0])

    def test_directory_query_and_pagination_are_server_side(self):
        response = self.client.get(
            "/api/v1/organizations/public-spaces/",
            {"q": "Visible", "page": "1", "page_size": "1"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["count"], 1)
        self.assertFalse(response.json()["data"]["has_next"])
        response = self.client.get(
            "/api/v1/organizations/public-spaces/",
            {"page": "0"},
        )
        self.assertEqual(response.status_code, 400)

    def test_public_category_and_city_filters_are_server_side(self):
        self.visible.archetype = SpaceArchetype.COMMUNITY
        self.visible.save(update_fields=["archetype"])
        second = Organization.objects.create(
            name="Creative Public Space",
            archetype=SpaceArchetype.CREATIVE,
            city="Kinshasa",
            country="RDC",
            created_by=self.owner,
        )
        endpoint = "/api/v1/organizations/public-spaces/"
        response = self.client.get(endpoint, {
            "category": SpaceArchetype.COMMUNITY,
            "city": "lubumbashi",
            "country": "rdc",
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["results"][0]["slug"], self.visible.slug)
        self.assertIn(
            {"value": SpaceArchetype.COMMUNITY, "label": SpaceArchetype.COMMUNITY.label},
            data["categories"],
        )
        response = self.client.get(endpoint, {"category": SpaceArchetype.CREATIVE})
        self.assertEqual(response.json()["data"]["results"][0]["slug"], second.slug)
        for partial in ("L", "Lu", "Lub", "Lubu", "Lubumbashi"):
            with self.subTest(partial=partial):
                response = self.client.get(endpoint, {"city": partial})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["data"]["count"], 1)
                self.assertEqual(
                    response.json()["data"]["results"][0]["slug"],
                    self.visible.slug,
                )
        response = self.client.get(endpoint, {"city": "shas"})
        self.assertEqual(response.json()["data"]["count"], 1)
        response = self.client.get(endpoint, {"city": "Kolwezi"})
        self.assertEqual(response.json()["data"]["count"], 0)
        response = self.client.get(endpoint, {"category": "not-a-category"})
        self.assertEqual(response.status_code, 400)
        response = self.client.get(endpoint, {"category": SpaceArchetype.COMMUNITY, "page": "2", "page_size": "1"})
        self.assertEqual(response.json()["data"]["count"], 1)
        self.assertEqual(response.json()["data"]["results"], [])

    def test_hidden_inactive_or_not_searchable_spaces_have_no_public_detail(self):
        for space in (self.private, self.hidden, self.inactive):
            with self.subTest(space=space.slug):
                response = self.client.get(
                    f"/api/v1/organizations/public-spaces/{space.slug}/"
                )
                self.assertEqual(response.status_code, 404)

    @patch("organizations.api.public_space_views.project_rows")
    @patch("organizations.api.public_space_views.compose_discovery")
    def test_detail_only_composes_items_from_canonical_public_field(
        self, compose, project
    ):
        own_activity = Activity.objects.create(
            space=self.visible,
            created_by=self.owner,
            title="Activite du Space",
        )
        other_activity = Activity.objects.create(
            space=self.private,
            created_by=self.owner,
            title="Activite privee",
        )
        compose.return_value = SimpleNamespace(rows=(
            ("activity", "a", {"activity_id": str(own_activity.pk)}),
            ("activity", "b", {"activity_id": str(other_activity.pk)}),
        ))
        project.side_effect = lambda rows, **kwargs: [
            {"activity_id": row[2]["activity_id"]} for row in rows
        ]
        response = self.client.get(
            f"/api/v1/organizations/public-spaces/{self.visible.slug}/"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["space"]["name"], self.visible.name)
        self.assertEqual(data["possibilities"]["count"], 1)
        self.assertEqual(
            data["possibilities"]["results"][0]["activity_id"],
            str(own_activity.pk),
        )
        compose.assert_called_once_with({}, profile=None)
        project.assert_called_once()
