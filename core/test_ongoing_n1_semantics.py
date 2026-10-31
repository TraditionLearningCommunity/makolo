"""OngoingMe N1: owner-backed cues and shared Web/Flutter display contract."""
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.test import SimpleTestCase
from django.utils import timezone

from core.api.personal_projections import (
    _attach_ongoing_recognition_media,
    _decorate_ongoing_semantics,
    _ongoing_n1_when,
)
from core.mature_experience_views import MatureParticipantOngoingView


class OngoingN1SemanticsTests(SimpleTestCase):
    def item(self, **overrides):
        item = {
            "kind": "journey",
            "source": {"kind": "journey", "id": "fixture-journey"},
            "state": "waiting",
            "title": "Visa Canada",
            "summary": "Demande en examen.",
            "ready": [],
            "actor_interventions": [],
            "continuation": {"state": "waiting", "summary": "Le consulat examine la demande."},
            "blocker": None,
            "next": {"title": "Biométrie"},
            "timing": {"start_date": "2026-11-15"},
            "place": {"name": "Centre de biométrie"},
            "capabilities": [],
            "links": {"web": "/me/ongoing/sample/"},
        }
        item.update(overrides)
        _decorate_ongoing_semantics(item, observed_at=timezone.now())
        return item

    def test_calm_wait_and_web_parity(self):
        item = self.item()
        self.assertEqual(item["n1"]["cue"], "En attente")
        self.assertEqual(item["n1"]["tone"], "calm")
        self.assertEqual(item["n1"]["when_label"], "15/11/2026")
        self.assertEqual(item["n1"]["supporting"], "Biométrie")
        self.assertEqual(item["media_bindings"], [])
        web = MatureParticipantOngoingView._web_item(item)
        self.assertEqual(web["title"], item["human_context"])
        self.assertEqual(web["summary"], item["synthesis"])
        self.assertEqual(web["cue"], item["n1"]["cue"])

    def test_personal_action_is_not_urgent_or_blocked(self):
        item = self.item(
            actor_interventions=[{"title": "Fournir un document"}],
            continuation=None,
        )
        self.assertEqual(item["n1"]["cue"], "De votre côté")
        self.assertEqual(item["n1"]["tone"], "action")

    def test_blocker_is_local_to_one_step(self):
        item = self.item(blocker={"title": "Pièce manquante"})
        self.assertEqual(item["n1"]["cue"], "Une étape bloquée")

    def test_no_fabricated_next_date_or_media(self):
        item = self.item(
            next=None, timing={}, place=None, continuation=None, state="active"
        )
        self.assertIsNone(item["n1"]["cue"])
        self.assertIsNone(item["n1"]["when_label"])
        self.assertIsNone(item["n1"]["supporting"])
        self.assertEqual(item["media_bindings"], [])

    def test_human_time_obeys_source_timezone(self):
        self.assertEqual(
            _ongoing_n1_when({
                "start_at": "2026-11-15T14:30:00+00:00",
                "timezone": "Africa/Kinshasa",
            }),
            "15/11/2026 · 15:30",
        )
        self.assertIsNone(_ongoing_n1_when({"start_at": "bad timestamp"}))

    def test_private_activity_does_not_gain_share_save_or_media(self):
        entry = SimpleNamespace(
            kind="journey",
            value=SimpleNamespace(activity_id=uuid4(), occurrence_id=None),
        )
        item = {
            "id": "private-continuity",
            "n1": {"cue": None},
            "media_bindings": [],
        }
        with patch("activities.models.Activity.objects.filter") as candidates:
            candidates.return_value.select_related.return_value = []
            _attach_ongoing_recognition_media(
                [entry], [item],
                viewer=SimpleNamespace(pk=uuid4()),
            )
        self.assertNotIn("possibility", item["n1"])
        self.assertEqual(item["media_bindings"], [])

