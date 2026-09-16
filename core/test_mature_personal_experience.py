from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from organizations.models import Organization, Team, TeamMembership, TeamMembershipStatus


User = get_user_model()


class MaturePersonalExperienceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="mature-personal",
            email="mature-personal@example.test",
            password="Strong-Mature-Password-2026!",
        )
        self.client.force_login(self.user)

    def test_primary_personal_destinations_render(self):
        expectations = {
            "core:participant-home": "Tout est en ordre. ✓",
            "core:participant-ongoing": "Ce qui continue",
            "core:participant-me": "Passeport Makolo",
            "core:makolo-mark": "Qu’est-ce que vous avez en tête ?",
        }
        for route_name, text in expectations.items():
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, text)

    def test_membership_is_visible_as_collective_but_not_as_authorized_space(self):
        owner = User.objects.create_user(
            username="mature-space-owner",
            email="mature-space-owner@example.test",
            password="Strong-Mature-Owner-2026!",
        )
        space = Organization.objects.create(name="Collectif sans autorité", created_by=owner)
        team = Team.objects.create(organization=space, name="Équipe membre", is_default=True)
        TeamMembership.objects.create(
            team=team,
            user=self.user,
            status=TeamMembershipStatus.ACTIVE,
            invited_by=owner,
        )

        response = self.client.get(reverse("core:participant-me"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["authorized_spaces"]), [])
        self.assertEqual([membership.team_id for membership in response.context["team_memberships"]], [team.pk])
        self.assertContains(response, "Équipe membre")
        self.assertNotContains(response, "Vous pouvez agir dans cet Espace")

    def test_mark_routes_explicit_discovery_intent_without_persisting_input(self):
        response = self.client.post(
            reverse("core:makolo-mark"),
            {"intent": "Je cherche quelque chose à faire ce soir"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(f"{reverse('discovery:home')}?q="))

    def test_mark_routes_explicit_continuity_intent(self):
        response = self.client.post(
            reverse("core:makolo-mark"),
            {"intent": "Où en est ma demande ?"},
        )

        self.assertRedirects(response, reverse("core:participant-ongoing"), fetch_redirect_response=False)

    def test_mark_asks_for_clarification_when_intent_is_ambiguous(self):
        response = self.client.post(
            reverse("core:makolo-mark"),
            {"intent": "J’ai reçu quelque chose"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Qu’est-ce que vous voulez obtenir à partir de ça ?")
        self.assertContains(response, "Explorer des possibilités")
        self.assertContains(response, "Reprendre quelque chose")
        self.assertContains(response, "Retrouver ce que j’ai déjà")
