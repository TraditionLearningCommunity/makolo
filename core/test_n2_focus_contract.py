"""N2 is a native composition of already-authorized N1 facts, not a new owner."""
import json
from pathlib import Path

from django.template.loader import render_to_string
from django.test import SimpleTestCase

from core.home_views import _now_web_context
from core.mature_experience_views import MatureParticipantOngoingView


FIXTURE = Path(__file__).resolve().parent.parent / "mobile/test/fixtures/now_s1_s5_contract.json"


class NowN2GoldenContractTests(SimpleTestCase):
    def test_all_five_now_topologies_produce_human_n2(self):
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        expected = ("meaning", "media", "action", "waiting", "composition")
        rendered = []
        for item, topology in zip(fixture["items"], expected, strict=True):
            projected = _now_web_context({
                **fixture, "items": [item]
            }).primary_attention
            self.assertEqual(projected.topology, topology)
            html = render_to_string(
                "core/_now_n2_focus.html", {"item": projected}
            )
            self.assertIn(item["human_context"], html)
            self.assertNotIn("source_domain", html)
            self.assertNotIn("context_type", html)
            rendered.append(html)
        self.assertIn("Pièce autorisée", rendered[1])
        self.assertIn("En attente", rendered[3])
        self.assertIn("Rendez-vous A", rendered[4])
        self.assertIn("Rendez-vous B", rendered[4])

    def test_now_n2_does_not_invent_an_action_or_private_share(self):
        home = _now_web_context({
            "items": [{
                "id": "private",
                "human_context": "Demande personnelle",
                "state_meaning": "Une réponse est attendue.",
                "response": {"type": "wait"},
                "business_actions": [],
                "links": {},
            }],
            "selection": {"state": "ready"},
            "freshness": {"state": "fresh"},
            "terminal": {"state": "ok"},
        })
        html = render_to_string(
            "core/_now_n2_focus.html", {"item": home.primary_attention}
        )
        self.assertIn("En attente", html)
        self.assertNotIn('data-now-direct', html)
        self.assertNotIn("Partager", html)

    def test_ongoing_n2_reuses_only_owner_projection_and_its_handoff(self):
        item = MatureParticipantOngoingView._web_item({
            "id": "ongoing-private",
            "kind": "journey",
            "source": {"kind": "journey", "id": "11111111-2222-4333-8444-555555555555"},
            "title": "Visa Canada",
            "summary": "Une réponse est attendue.",
            "settled": [{"title": "Formulaire transmis"}],
            "my_side": [{"title": "Fournir le certificat"}],
            "elsewhere": [{"summary": "Examen par le consulat"}],
            "next_items": [{"title": "Biométrie"}],
            "links": {},
        })
        html = render_to_string("core/_ongoing_n2_focus.html", {"item": item})
        for phrase in ("Visa Canada", "Formulaire transmis",
                       "Fournir le certificat", "Examen par le consulat", "Biométrie"):
            self.assertIn(phrase, html)
        self.assertNotIn("Ouvrir la démarche", html)
        self.assertNotIn("Partager", html)
