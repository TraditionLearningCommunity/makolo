from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.urls import resolve, reverse

from objectives.models import Dossier, Project
from organizations.models import Organization

from .personal_navigation import personal_surface_owner


User = get_user_model()


class PersonalUXFinalClosureTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="personal-closure",
            email="personal-closure@example.test",
            password="StrongPass2026!",
        )
        self.factory = RequestFactory()

    def _surface(self, route_name, *args):
        path = reverse(route_name, args=args)
        request = self.factory.get(path)
        request.user = self.user
        request.resolver_match = resolve(path)
        return personal_surface_owner(request)

    def test_personal_primary_navigation_remains_exactly_five_surfaces(self):
        expected = {
            "core:participant-home": "now",
            "discovery:home": "discover",
            "core:makolo-mark": "mark",
            "core:participant-ongoing": "ongoing",
            "core:participant-me": "me",
        }
        for route, owner in expected.items():
            surface = self._surface(route)
            self.assertEqual(surface.owner, owner)
            self.assertEqual(surface.level, "n1")
            self.assertTrue(surface.is_primary)

    def test_saved_items_and_watches_belong_to_me_not_discover(self):
        for route in (
            "discovery:bookmarks",
            "discovery:watch-list",
        ):
            surface = self._surface(route)
            self.assertEqual(surface.owner, "me")
            self.assertEqual(surface.level, "n2")
            self.assertEqual(surface.back_url, reverse("core:participant-me"))

        watch = self._surface("discovery:watch-detail", uuid4())
        self.assertEqual(watch.owner, "me")
        self.assertEqual(watch.level, "n3")

    def test_operator_and_staff_routes_are_not_absorbed_by_personal_navigation(self):
        for route, args in (
            ("services:operator-dashboard", ()),
            ("opportunities:staff-dashboard", ()),
            ("funding:manage", (uuid4(),)),
        ):
            with self.subTest(route=route):
                surface = self._surface(route, *args)
                self.assertIsNone(surface.owner)
                self.assertFalse(surface.is_primary)

    def test_group_context_belongs_to_me_without_granting_space_authority(self):
        surface = self._surface("social:group", "collectif-test")
        self.assertEqual(surface.owner, "me")
        self.assertEqual(surface.level, "n3")

    def test_retired_generic_action_stream_redirects_to_maintenant(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("social:network"))
        self.assertRedirects(response, reverse("core:participant-home"))

    def test_personal_dossier_creation_cannot_be_switched_to_space_by_post_data(self):
        space = Organization.objects.create(name="Space dossier", created_by=self.user)
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("objectives:dossier-create"),
            {
                "title": "Mon objectif personnel",
                "description": "Personnel",
                "deadline": "",
                "owning_space": str(space.pk),
            },
        )
        dossier = Dossier.objects.get(title="Mon objectif personnel")
        self.assertRedirects(
            response,
            reverse("objectives:dossier-detail", args=[dossier.pk]),
        )
        self.assertEqual(dossier.owner_profile_id, self.user.pk)
        self.assertIsNone(dossier.owning_space_id)

    def test_personal_project_creation_cannot_be_switched_to_space_by_post_data(self):
        space = Organization.objects.create(name="Space project", created_by=self.user)
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("objectives:project-create"),
            {
                "title": "Mon horizon personnel",
                "description": "Personnel",
                "starts_on": "",
                "ends_on": "",
                "owning_space": str(space.pk),
            },
        )
        project = Project.objects.get(title="Mon horizon personnel")
        self.assertRedirects(
            response,
            reverse("objectives:project-detail", args=[project.pk]),
        )
        self.assertEqual(project.owner_profile_id, self.user.pk)
        self.assertIsNone(project.owning_space_id)
