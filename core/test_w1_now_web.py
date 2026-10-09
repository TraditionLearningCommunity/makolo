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

    def test_wait_is_explicit_and_never_inferred_from_state(self):
        pending = _now_web_context(
            _response(items=[{
                "id": "waiting", "title": "Demande", "state": "waiting",
                "state_meaning": "La demande est en cours.",
                "response": {"type": "wait"},
                "turn": {"label": "Fournisseur"},
                "horizon": {"text": "Jusqu'à sa réponse"},
            }])
        ).primary_attention
        self.assertEqual(pending.topology, "waiting")
        self.assertEqual(pending.horizon, "Jusqu'à sa réponse")
        no_contract = _now_web_context(
            _response(items=[{
                "id": "not-wait", "title": "Demande", "state": "waiting",
            }])
        ).primary_attention
        self.assertEqual(no_contract.topology, "meaning")

    def test_media_is_access_denied_by_default(self):
        item = {
            "id": "media", "title": "Certificat", "state_meaning": "Disponible",
            "media_bindings": [
                {"resource_ref": "proof:private", "kind": "pdf", "purpose": "understand"},
                {"resource_ref": "proof:visible", "kind": "pdf", "purpose": "understand",
                 "authorized": True, "label": "Document autorisé"},
            ],
        }
        view = _now_web_context(_response(items=[item])).primary_attention
        self.assertEqual(view.topology, "media")
        self.assertEqual(view.media_labels, ("Document autorisé",))

    def test_relation_without_owner_consequence_cannot_dominate(self):
        item = {
            "id": "relation", "title": "Conflit",
            "state_meaning": "Deux engagements",
            "relation_members": [{"id": "a"}, {"id": "b"}],
            "relations": [{"summary": "Même heure", "kind": "conflict"}],
            "response": {"type": "decide"},
        }
        view = _now_web_context(_response(items=[item])).primary_attention
        self.assertEqual(view.topology, "meaning")
        item["why_now"] = {"meaning": "Ils commencent ensemble"}
        item["consequence"] = {"effect": "Une présence simultanée est impossible"}
        view = _now_web_context(_response(items=[item])).primary_attention
        self.assertEqual(view.topology, "composition")

    def test_inline_reader_is_first_party_and_owner_authorized_only(self):
        from uuid import uuid4

        artifact_id = str(uuid4())
        safe = f"/api/v1/me/now/media/journey-artifacts/{artifact_id}/"
        item = {
            "id": "now:media",
            "title": "Pièce liée à la démarche",
            "media_bindings": [
                {"resource_ref": "file:unapproved", "authorized": False,
                 "kind": "pdf", "url": safe},
                {"resource_ref": "file:external", "authorized": True,
                 "kind": "image", "url": "https://external.invalid/private.jpg"},
                {"resource_ref": "file:traversal", "authorized": True,
                 "kind": "pdf", "url": "/api/v1/me/now/media/journey-artifacts/../"},
                {"resource_ref": "file:approved", "authorized": True,
                 "kind": "pdf", "url": safe, "label": "Document autorisé"},
            ],
        }
        view = _now_web_context(_response(items=[item])).primary_attention
        self.assertEqual(
            view.inline_media,
            ({"url": safe, "kind": "pdf", "label": "Document autorisé"},),
        )

    def test_inline_document_only_accepts_bounded_text_preview(self):
        from uuid import uuid4

        identifier = str(uuid4())
        path = f"/api/v1/me/now/media/journey-artifacts/{identifier}/"
        item = {
            "id": "now:doc",
            "title": "Document",
            "media_bindings": [
                {"resource_ref": "file:document", "authorized": True,
                 "kind": "document", "url": path + "?view=text"},
                {"resource_ref": "file:unsafe", "authorized": True,
                 "kind": "document", "url": path + "?view=admin"},
            ],
        }
        view = _now_web_context(_response(items=[item])).primary_attention
        self.assertEqual(len(view.inline_media), 1)
        self.assertEqual(view.inline_media[0]["url"], path + "?view=text")

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
