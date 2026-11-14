"""N2 is a read-only owner projection, never a universal alternative score."""
from django.test import SimpleTestCase
from django.urls import reverse

from .n2_presentation import build_n2_presentation


class DiscoveryN2PresentationTests(SimpleTestCase):
    def _base(self, *, family="activity"):
        return {"identity": {
            "family": family,
            "resource": {"kind": "activity", "id": "parent"},
        }}

    def test_assessment_unknown_is_not_false_and_duplicate_labels_are_bounded(self):
        projection = self._base()
        projection["assessment"] = [
            {"state": "favorable", "label": "Disponible"},
            {"state": "limiting", "label": "Dernières places"},
            {"state": "unknown", "label": "Votre éligibilité reste inconnue"},
            {"state": "unknown", "label": "Votre éligibilité reste inconnue"},
            {"state": "unsupported", "label": "UX inference"},
        ]
        n2 = build_n2_presentation(projection)
        self.assertEqual(n2["assessment"]["favorable"], ["Disponible"])
        self.assertEqual(n2["assessment"]["limiting"], ["Dernières places"])
        self.assertEqual(n2["assessment"]["unknown"], ["Votre éligibilité reste inconnue"])
        self.assertFalse(n2["comparison"])

    def test_variants_can_compare_only_complete_shared_owner_dimensions(self):
        projection = self._base()
        projection.update({
            "price": {"state": "fixed", "amount": 90, "currency": "USD"},
            "variants": [
                {"occurrence": {"kind": "occurrence", "id": "morning"},
                 "timing": {"start_date": "2026-11-12", "start_time": "09:00"}},
                {"occurrence": {"kind": "occurrence", "id": "evening"},
                 "timing": {"start_date": "2026-11-12", "start_time": "17:00"}},
                {"occurrence": {"kind": "occurrence", "id": "morning"},
                 "timing": {"start_date": "2026-11-13"}},
            ],
            "spatial_facts": [
                {"occurrence": {"kind": "occurrence", "id": "morning"},
                 "place": {"name": "Campus A", "locality": "Lubumbashi"}},
                {"occurrence": {"kind": "occurrence", "id": "evening"},
                 "place": {"name": "Campus B", "locality": "Lubumbashi"}},
            ],
        })
        n2 = build_n2_presentation(projection)
        self.assertEqual(len(n2["variants"]), 2)
        self.assertEqual(n2["variants"][0]["places"], ("Campus A, Lubumbashi",))
        self.assertEqual(n2["variants"][1]["places"], ("Campus B, Lubumbashi",))
        self.assertEqual([row["label"] for row in n2["comparison"]], ["Début", "Lieu"])
        self.assertEqual(n2["comparison"][0]["values"],
                         ("2026-11-12 · 09:00", "2026-11-12 · 17:00"))

    def test_absent_or_foreign_facts_do_not_create_comparison(self):
        for family in ("funding_activity", "service_activity", "opportunity"):
            projection = self._base(family=family)
            projection["variants"] = [
                {"occurrence": {"kind": "occurrence", "id": "one"},
                 "timing": {"start_date": "2026-11-01"}},
                {"occurrence": {"kind": "occurrence", "id": "two"},
                 "timing": {"start_date": "2026-11-02"}},
            ]
            n2 = build_n2_presentation(projection)
            self.assertFalse(n2["comparison"])
            self.assertFalse(n2["variants"])
        projection = self._base()
        projection["variants"] = [
            {"occurrence": {"kind": "occurrence", "id": "one"},
             "timing": {"start_date": "2026-11-01"}},
            {"occurrence": {"kind": "occurrence", "id": "two"},
             "timing": {}},
        ]
        self.assertFalse(build_n2_presentation(projection)["comparison"])

    def test_complement_is_not_reclassified_as_alternative(self):
        projection = self._base()
        projection["relations"] = [
            {"label": "Peut aider à financer la formation", "kind": "complement"},
            {"kind": "alternative", "target": {"kind": "activity", "id": "two"}},
        ]
        n2 = build_n2_presentation(projection)
        self.assertEqual(n2["relations"], ("Peut aider à financer la formation",))
        self.assertFalse(n2["comparison"])

    def test_route_is_specific_to_an_admitted_owner_detail(self):
        path = reverse("discovery:possibility-detail", kwargs={
            "family": "activity", "item_id": "abc",
        })
        self.assertEqual(path, "/discover/possibilities/activity/abc/")
