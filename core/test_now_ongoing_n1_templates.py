"""Presentation tests: both personal N1 streams reuse their owner projections."""
from django.template.loader import render_to_string
from django.test import SimpleTestCase

from core.home_views import _now_web_context
from core.mature_experience_views import MatureParticipantOngoingView


class PersonalN1TemplateTests(SimpleTestCase):
    def test_now_fragment_exposes_server_cursor_and_complete_unit(self):
        situation = {
            "id": "nown1-one",
            "key": "nown1-one",
            "human_context": "Inscription",
            "title": "Votre inscription",
            "state_meaning": "Un document est à vérifier.",
            "summary": "Un document est à vérifier.",
            "response": {"type": "understand", "label": "Vérifier"},
            "why_now": {"meaning": "Une pièce est demandée."},
            "consequence": {"state": "unknown", "effect": None},
            "source": {"kind": "journey", "id": "11111111-2222-4333-8444-555555555555"},
        }
        projection = {
            "items": [situation],
            "selection": {"state": "ready"},
            "freshness": {"state": "fresh"},
            "actor_attention_state": "active",
            "terminal": {"state": "ok"},
            "continuation": {"state": "more", "token": "opaque-test-next"},
        }
        home = _now_web_context(projection)
        html = render_to_string("core/_now_page_fragment.html", {"home": home})
        self.assertIn('data-next-token="opaque-test-next"', html)
        self.assertIn('data-continuation-state="more"', html)
        self.assertIn('data-now-identity="nown1-one"', html)
        self.assertIn("Voir plus", html)
        self.assertIn("Voir moins", html)
        self.assertIn("Un document est à vérifier.", html)

    def test_ongoing_fragment_has_single_unit_and_server_continuity(self):
        item = {
            "id": "ongoing-1",
            "source": {"kind": "journey", "id": "11111111-2222-4333-8444-555555555555"},
            "kind": "journey",
            "title": "Inscription",
            "human_context": "Inscription",
            "summary": "Une réponse est attendue.",
            "synthesis": "Une réponse est attendue.",
            "settled": [{"title": "Dossier remis"}],
            "my_side": [{"title": "Valider le reçu"}],
            "elsewhere": [{"summary": "L'organisme répondra."}],
            "next_items": [],
            "links": {"web": "/me/journeys/11111111-2222-4333-8444-555555555555/"},
            "n1": {"tone": "calm", "cue": "En attente"},
        }
        projected = MatureParticipantOngoingView._web_item(item)
        html = render_to_string(
            "core/_ongoing_page_fragment.html",
            {
                "ongoing_items": [projected],
                "ongoing_next_token": "cursor",
            },
        )
        self.assertIn('data-next-token="cursor"', html)
        self.assertEqual(html.count('data-ongoing-unit'), 1)
        self.assertIn("Dossier remis", html)
        self.assertIn("Valider le reçu", html)
        self.assertIn("Voir moins", html)
        self.assertIn("Continuer la démarche", html)
        self.assertIn("Enregistrer", html)
        self.assertIn("Partager", html)

    def test_published_discovery_owner_reuses_n1_save_and_sharing(self):
        activity_id = "11111111-2222-4333-8444-555555555555"
        item = {
            "id": "ongoing-public",
            "kind": "journey",
            "title": "Visite guidée",
            "summary": "Départ confirmé.",
            "links": {"web": "/me/ongoing/visite/"},
            "n1": {
                "possibility": {
                    "family": "activity",
                    "id": activity_id,
                    "saved_state": "not_saved",
                    "capabilities": ["save", "share"],
                    "links": {
                        "saved": (
                            f"/api/v1/discovery/items/activity/{activity_id}/saved/"
                        ),
                        "share": (
                            f"/api/v1/sharing/possibilities/activity/{activity_id}/"
                        ),
                    },
                },
            },
        }
        projected = MatureParticipantOngoingView._web_item(item)
        html = render_to_string("core/_ongoing_unit.html", {"item": projected})
        self.assertIn("data-ongoing-save", html)
        self.assertIn("data-makolo-share", html)
        self.assertIn("Voir plus", html) if projected["details"] else None
        self.assertIn("Enregistrer", html)
        self.assertIn("Continuer la démarche", html)
        self.assertIn("Partager", html)

    def test_private_continuity_does_not_gain_public_share_or_save(self):
        item = {
            "id": "private",
            "kind": "journey",
            "title": "Démarche personnelle",
            "summary": "À préparer.",
            "settled": [],
            "my_side": [],
            "elsewhere": [],
            "next_items": [],
            "links": {},
        }
        projected = MatureParticipantOngoingView._web_item(item)
        html = render_to_string(
            "core/_ongoing_unit.html", {"item": projected}
        )
        self.assertIn("Partager", html)
        self.assertIn("Enregistrer", html)
        self.assertIn("mk-ongoing-unit__action-disabled", html)
        self.assertNotIn("data-makolo-share", html)
        self.assertNotIn("data-ongoing-save", html)
