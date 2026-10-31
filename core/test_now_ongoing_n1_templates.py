"""Presentation tests: both personal N1 streams reuse their owner projections."""
from django.template.loader import render_to_string
from django.test import SimpleTestCase

from core.home_views import _now_web_context, _now_inline_media, _now_topology
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

    def test_now_public_recognition_media_requires_exact_published_binding(self):
        use_id = "11111111-2222-4333-8444-555555555555"
        url = f"/presentation/media/uses/{use_id}/file/"
        valid = {
            "resource_ref": f"presentation_media_use:{use_id}",
            "target": "subject",
            "purpose": "recognize",
            "kind": "image",
            "url": url,
            "label": "Véhicule",
            "authorized": True,
            "presentation_rank": "primary",
        }
        self.assertEqual(_now_inline_media({"media_bindings": [valid]})[0]["url"], url)
        for altered in (
            {**valid, "authorized": False},
            {**valid, "url": "https://example.test" + url},
            {**valid, "url": url + "?token=secret"},
            {**valid, "resource_ref": "journey_artifact:" + use_id},
        ):
            self.assertFalse(_now_inline_media({"media_bindings": [altered]}))

    def test_now_s2_renders_published_recognition_image(self):
        use_id = "11111111-2222-4333-8444-555555555555"
        situation = {
            "id": "now-image",
            "key": "now-image",
            "human_context": "Voyage Kolwezi",
            "state_meaning": "Le départ est à préparer.",
            "response": {"type": "prepare", "label": "Préparer"},
            "media_bindings": [{
                "resource_ref": f"presentation_media_use:{use_id}",
                "target": "subject", "purpose": "recognize", "kind": "image",
                "url": f"/presentation/media/uses/{use_id}/file/",
                "authorized": True, "presentation_rank": "primary",
                "label": "Véhicule de la liaison",
            }],
        }
        self.assertEqual(_now_topology(situation), "media")
        home = _now_web_context({
            "items": [situation], "selection": {"state": "ready"},
            "freshness": {"state": "fresh"},
            "actor_attention_state": "active",
            "terminal": {"state": "ok"},
        })
        html = render_to_string("core/_now_page_fragment.html", {"home": home})
        self.assertIn("mk-now-unit__hero", html)
        self.assertIn(f"/presentation/media/uses/{use_id}/file/", html)

    def test_now_web_s5_preserves_relation_and_semantic_fields(self):
        situation = {
            "id": "now-composition",
            "key": "now-composition",
            "human_context": "Réservations",
            "state_meaning": "Deux rendez-vous se chevauchent.",
            "subject": {"label": "Disponibilité"},
            "delta": {"meaning": "Le second horaire est confirmé."},
            "exit_condition": {"label": "Un créneau est libéré."},
            "why_now": {"meaning": "Les horaires se recouvrent."},
            "consequence": {"state": "known", "effect": "Un seul rendez-vous est possible."},
            "response": {"type": "decide", "label": "Choisir"},
            "relation_members": [
                {"id": "a", "label": "Rendez-vous A"},
                {"id": "b", "label": "Rendez-vous B"},
            ],
            "relations": [{"kind": "conflict", "member_ids": ["a", "b"],
                           "summary": "Même créneau."}],
            "media_bindings": [{
                "resource_ref": "presentation_media_use:11111111-2222-4333-8444-555555555555",
                "target": "subject", "purpose": "recognize", "kind": "image",
                "url": "/presentation/media/uses/11111111-2222-4333-8444-555555555555/file/",
                "authorized": True, "presentation_rank": "primary",
            }],
        }
        self.assertEqual(_now_topology(situation), "composition")
        home = _now_web_context({
            "items": [situation],
            "selection": {"state": "ready"},
            "freshness": {"state": "fresh"},
            "actor_attention_state": "active",
            "terminal": {"state": "ok"},
        })
        html = render_to_string("core/_now_page_fragment.html", {"home": home})
        self.assertIn("Disponibilité", html)
        self.assertIn("Le second horaire est confirmé.", html)
        self.assertIn("Rendez-vous A", html)

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
