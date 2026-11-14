"""Targeted LP5 protection: dynamic copy follows facts and provenance."""

from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.test import SimpleTestCase

from core.api.personal_projections import _dossier_ongoing_item
from core.participant_action_presentation import _access_presentation
from readiness import ReadinessStatus
from discovery.api.composition import _assessment, _opportunity_source_previews


class ServerProductLanguageTests(SimpleTestCase):
    def test_live_access_advice_does_not_expose_occurrence(self):
        ready = _access_presentation([{"usable": True, "status": "valid"}])
        self.assertEqual(ready["state"], "ready")
        self.assertEqual(ready["detail"], "Vous pouvez présenter cet accès au moment prévu.")
        self.assertNotIn("occurrence", ready["detail"].lower())

        not_ready = _access_presentation([{"usable": False, "status": "revoked"}])
        self.assertEqual(not_ready["state"], "unavailable")
        self.assertIn("vérifier ce qui manque avant de vous déplacer", not_ready["detail"])

    def test_discovery_unknown_relation_remains_unknown_not_a_denial(self):
        facts = _assessment({
            "availability": {"state": "unknown"},
            "personal_relation": {"state": "unknown"},
        })
        self.assertEqual([item["state"] for item in facts], ["unknown", "unknown"])
        self.assertIn("pas encore confirmé", facts[1]["label"])
        self.assertNotIn("impossible", facts[1]["label"].lower())

    def test_opportunity_source_is_not_automatically_endorsed(self):
        opportunity_id = uuid4()
        source = SimpleNamespace(
            pk=uuid4(),
            opportunity_id=opportunity_id,
            source_name="Catalogue indiqué",
            url="https://example.org/catalogue/",
        )
        with patch("opportunities.models.OpportunitySource.objects.filter") as query:
            query.return_value.order_by.return_value = [source]
            previews = _opportunity_source_previews([opportunity_id])
        shown = previews[str(opportunity_id)][0]
        self.assertEqual(shown["title"], "Catalogue indiqué")
        self.assertEqual(shown["external_url"], "https://example.org/catalogue/")
        self.assertEqual(shown["description"], "")

    def test_dossier_summary_follows_owner_readiness_without_a_parallel_status(self):
        dossier = SimpleNamespace(pk=uuid4(), title="Dossier formation", deadline=None)
        ready = SimpleNamespace(status=ReadinessStatus.READY, primary_next_action=None)
        item = _dossier_ongoing_item(dossier, readiness=ready)
        self.assertEqual(item["summary"], "Ce dossier est prêt pour la prochaine étape.")
        self.assertEqual(item["state"], ReadinessStatus.READY.value)
        self.assertNotIn("objectif composé", item["summary"])
