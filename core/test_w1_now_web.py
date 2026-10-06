from django.test import SimpleTestCase

from core.home_views import _now_web_context


def _response(**overrides):
    response = {
        "surface": "now_me",
        "freshness": {"state": "fresh", "observed_at": "2026-10-06T11:35:00Z"},
        "selection": {"state": "ready", "reason": None},
        "actor_attention_state": "active",
        "items": [],
        "continuation": None,
        "terminal": {"state": "ok", "message": None},
    }
    response.update(overrides)
    return response


class NowWebPresentationTests(SimpleTestCase):
    def test_empty_items_do_not_create_a_calm_claim(self):
        home = _now_web_context(_response())

        self.assertFalse(home.all_clear)
        self.assertFalse(home.is_calm)
        self.assertFalse(home.is_unavailable)

    def test_calm_requires_explicit_server_attention_and_terminal_states(self):
        home = _now_web_context(
            _response(
                actor_attention_state="calm",
                selection={"state": "empty", "reason": "no_current_attention_needed"},
                terminal={"state": "empty", "message": "Tout est en ordre. ✓"},
            )
        )

        self.assertTrue(home.all_clear)
        self.assertEqual(home.terminal_message, "Tout est en ordre. ✓")

    def test_partial_items_preserve_server_order_and_semantics(self):
        home = _now_web_context(
            _response(
                selection={"state": "partial", "reason": "owner_temporarily_missing"},
                items=[
                    {
                        "id": "now:first",
                        "key": "legacy-first",
                        "human_context": "Visa Canada",
                        "state": "journey.step.required",
                        "state_meaning": "Le certificat doit être transmis.",
                        "why_now": {
                            "reason": "deadline.due_today",
                            "meaning": "La fenêtre ferme aujourd’hui.",
                        },
                        "consequence": {"effect": "La demande peut rester bloquée."},
                        "turn": {"type": "profile"},
                        "response": {"type": "act", "label": "Vérifier et envoyer"},
                        "links": {"web": "/journeys/visa/"},
                    },
                    {
                        "id": "now:second",
                        "key": "legacy-second",
                        "title": "Comprendre le changement",
                        "response": {"type": "understand", "label": "Voir le détail"},
                        "links": {"detail": "/changes/2/"},
                    },
                ],
            )
        )

        self.assertTrue(home.is_partial)
        self.assertEqual(home.primary_attention.identity, "now:first")
        self.assertEqual(home.primary_attention.why_now, "La fenêtre ferme aujourd’hui.")
        self.assertEqual(
            home.primary_attention.consequence,
            "La demande peut rester bloquée.",
        )
        self.assertEqual(home.primary_attention.action_label, "Vérifier et envoyer")
        self.assertEqual(home.primary_attention.url, "/journeys/visa/")
        self.assertEqual([item.identity for item in home.action_items], ["now:second"])
        self.assertIsNone(home.primary_action)

    def test_machine_codes_and_unknown_consequence_are_not_presented_as_copy(self):
        home = _now_web_context(
            _response(
                items=[
                    {
                        "id": "now:unknown-consequence",
                        "key": "legacy-unknown-consequence",
                        "title": "Préparation",
                        "state": "requirement.pending",
                        "state_meaning": "Une préparation reste nécessaire.",
                        "why_now": {
                            "reason": "requirement.current",
                            "meaning": "Cette préparation est requise maintenant.",
                        },
                        "consequence": {
                            "state": "unknown",
                            "effect": "Ce texte ne doit pas être présenté.",
                        },
                        "response": {"type": "understand", "label": "Comprendre"},
                    }
                ]
            )
        )

        self.assertEqual(home.primary_attention.state, "Une préparation reste nécessaire.")
        self.assertEqual(
            home.primary_attention.why_now,
            "Cette préparation est requise maintenant.",
        )
        self.assertEqual(home.primary_attention.consequence, "")

    def test_missing_selection_is_unavailable_instead_of_calm(self):
        home = _now_web_context({"items": []})

        self.assertTrue(home.is_unavailable)
        self.assertFalse(home.all_clear)

    def test_stale_is_kept_distinct_from_server_partial(self):
        home = _now_web_context(
            _response(freshness={"state": "stale", "observed_at": None})
        )

        self.assertTrue(home.is_stale)
        self.assertFalse(home.is_partial)
