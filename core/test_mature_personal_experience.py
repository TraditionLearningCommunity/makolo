from unittest.mock import patch

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
            "core:participant-ongoing": "<h1>En cours</h1>",
            "core:participant-me": "Passeport Makolo",
            "core:makolo-mark": "Qu’est-ce que vous avez en tête ?",
        }
        for route_name, text in expectations.items():
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, text)

    def test_primary_shell_does_not_reintroduce_legacy_global_destinations(self):
        response = self.client.get(reverse("core:participant-home"))

        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        mobile_nav = html.split('id="mobile-primary-nav"', 1)[1].split("</nav>", 1)[0]
        for label in ("Maintenant", "Découvrir", "Makolo", "En cours", "Moi"):
            self.assertIn(f"<span>{label}</span>", mobile_nav)
        for legacy_label in ("Démarches", "Conversations", "Profil", "Plus"):
            self.assertNotIn(f"<span>{legacy_label}</span>", mobile_nav)

    def test_expanded_shell_exposes_workspace_foundation_without_changing_compact_navigation(self):
        response = self.client.get(reverse("core:participant-home"))

        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('class="mk-workspace"', html)
        self.assertIn('data-workspace-layout="focus"', html)
        self.assertIn('class="mk-workspace__primary"', html)
        self.assertIn('class="mk-sidebar-toggle mk-icon-btn"', html)
        self.assertIn('data-mk-runtime-scope="personal"', html)
        self.assertIn('workspace-runtime.', html)
        self.assertIn('id="mobile-primary-nav"', html)
        self.assertIn('md:hidden', html)

    def test_personal_surfaces_expose_their_expanded_compositions(self):
        now_response = self.client.get(reverse("core:participant-home"))
        ongoing_response = self.client.get(reverse("core:participant-ongoing"))
        me_response = self.client.get(reverse("core:participant-me"))

        self.assertContains(now_response, 'data-mk-surface="now"')
        self.assertContains(now_response, 'data-workspace-layout="focus"')
        self.assertContains(ongoing_response, 'data-workspace-layout="master-detail"')
        self.assertContains(ongoing_response, 'data-mk-surface="ongoing"')
        self.assertContains(me_response, 'data-mk-surface="me"')
        self.assertContains(me_response, 'class="mk-me-grid"')
        main_html = me_response.content.decode().split('<main', 1)[1].split('</main>', 1)[0]
        self.assertNotIn(self.user.email, main_html)
        self.assertContains(me_response, f"@{self.user.username}")

    def test_me_does_not_reduce_the_person_to_a_completion_score(self):
        response = self.client.get(reverse("core:participant-me"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "% activé")

    def test_ongoing_items_keep_a_compact_link_and_offer_an_expanded_detail_target(self):
        response = self.client.get(reverse("core:participant-ongoing"))

        self.assertEqual(response.status_code, 200)
        if response.context["ongoing_items"]:
            self.assertContains(response, 'class="mk-ongoing-card mk-ongoing-card--compact')
            self.assertContains(response, 'class="mk-ongoing-card mk-ongoing-card--expanded')
            self.assertContains(response, 'hx-target="#ongoing-detail-body"')
            self.assertContains(response, 'hx-push-url="false"')
            self.assertContains(response, 'id="ongoing-detail"')

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

    @patch("core.mature_experience_views.orchestrate_mark")
    def test_mark_web_clarification_can_submit_selected_owner_target(self, orchestrate):
        orchestrate.return_value = {
            "state": "needs_clarification",
            "message": "Laquelle voulez-vous ouvrir ?",
            "question": {
                "options": [
                    {"kind": "journey", "id": "selected-journey", "label": "Ma démarche"}
                ]
            },
        }
        response = self.client.post(
            reverse("core:makolo-mark"), {"intent": "Retrouve ma démarche"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ma démarche")
        self.assertContains(response, 'name="selected_id" value="selected-journey"')

        self.client.post(
            reverse("core:makolo-mark"),
            {
                "intent": "Retrouve ma démarche",
                "selected_kind": "journey",
                "selected_id": "selected-journey",
                "profile_id": "untrusted",
            },
        )
        self.assertEqual(
            orchestrate.call_args.kwargs["context"],
            {"selected": {"kind": "journey", "id": "selected-journey"}},
        )

    @patch("core.mature_experience_views.orchestrate_mark")
    def test_mark_web_recognition_confirmation_is_owner_scoped(self, orchestrate):
        orchestrate.return_value = {
            "state": "needs_confirmation",
            "message": "Vérifiez votre récompense.",
            "action": {
                "code": "redeem_recognition",
                "summary": "Utiliser cette récompense ?",
                "target": {"kind": "recognition_reward", "id": "reward-id"},
            },
        }
        response = self.client.post(
            reverse("core:makolo-mark"), {"intent": "Utilise ma récompense"}
        )
        self.assertContains(response, "Confirmer cette utilisation")
        self.assertContains(response, 'name="idempotency_key"')

        self.client.post(
            reverse("core:makolo-mark"),
            {
                "intent": "Utilise ma récompense",
                "selected_kind": "recognition_reward",
                "selected_id": "reward-id",
                "confirm_code": "redeem_recognition",
                "confirm_target_id": "reward-id",
                "idempotency_key": "a" * 32,
            },
        )
        self.assertEqual(
            orchestrate.call_args.kwargs["context"],
            {
                "selected": {"kind": "recognition_reward", "id": "reward-id"},
                "confirmation": {
                    "code": "redeem_recognition",
                    "target_id": "reward-id",
                },
                "idempotency_key": "a" * 32,
            },
        )

    def test_mark_web_does_not_silently_truncate_a_long_intention(self):
        original = "Je cherche " + "une activité " * 70
        response = self.client.post(
            reverse("core:makolo-mark"), {"intent": original}
        )
        self.assertEqual(response.status_code, 400)
        self.assertContains(
            response, "au maximum 600 caractères", status_code=400
        )
        self.assertContains(response, original, status_code=400)

    def test_mark_web_exposes_local_intake_and_desktop_without_faking_upload(self):
        response = self.client.get(reverse("core:makolo-mark"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-mk-mark-root')
        self.assertContains(response, 'data-mk-mark-float')
        self.assertContains(response, 'data-mk-mark-minimize')
        self.assertContains(response, 'data-mk-mark-restore')
        self.assertContains(response, 'data-mk-mark-files')
        self.assertContains(response, 'data-mk-mark-photo')
        self.assertContains(response, 'data-mk-mark-voice')
        self.assertContains(response, 'data-mk-mark-link-input')
        self.assertContains(response, 'data-mk-mark-text-consent')
        self.assertContains(response, 'mark-intake.js')
        self.assertContains(response, 'mark-intake.css')
        # Browser file pickers deliberately have no multipart upload name;
        # the Mark owner contract stays text-only.
        self.assertNotContains(response, 'name="attachments"')
        self.assertIn("no-store", response["Cache-Control"])

    def test_mark_web_does_not_imply_uploaded_file_from_untrusted_form_field(self):
        with patch("core.mature_experience_views.orchestrate_mark") as route:
            route.return_value = {
                "state": "unsupported",
                "message": "Cette entrée n'est pas encore prise en charge.",
            }
            response = self.client.post(
                reverse("core:makolo-mark"),
                {
                    "intent": "Prépare cette demande",
                    "input_kind": "document",
                    "media_uploaded": "true",
                    "attachment_ids": "fake-asset-id",
                },
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(route.call_args.kwargs["input_kind"], "text")
            self.assertEqual(route.call_args.kwargs["context"], {})
