"""Presentation-only tests: grouping may not change owner scope or targets."""
from django.test import SimpleTestCase

from core.retrieval_presentation import group_retrieval_rows


class RetrievalPresentationTests(SimpleTestCase):
    def test_distinct_person_relations_stay_distinct_and_human_grouped(self):
        rows = [
            {
                "source": {"kind": "team_member", "id": "one"},
                "title": "Marie Kalala",
                "human_type": "Collaboratrice · Équipe",
                "destination": "/spaces/example/relationships/?kind=team_member&id=one",
            },
            {
                "source": {"kind": "crm_contact", "id": "two"},
                "title": "Marie Kalala",
                "human_type": "Contact CRM",
                "destination": "/spaces/example/relationships/?kind=crm_contact&id=two",
            },
        ]
        groups = group_retrieval_rows(rows, context={"q": "Marie", "page": 2})
        self.assertEqual([g["label"] for g in groups], [
            "Collaboratrice · Équipe", "Contact CRM",
        ])
        self.assertEqual(sum(len(g["items"]) for g in groups), 2)
        self.assertIn("selected=crm_contact%3Atwo", groups[1]["items"][0]["web_destination"])
        self.assertIn("page=2", groups[1]["items"][0]["web_destination"])
        self.assertIn("kind=crm_contact", groups[1]["items"][0]["web_destination"])

    def test_history_labels_and_owner_return_filters(self):
        rows = [{
            "source": {"kind": "occurrence", "id": "past-one"},
            "title": "Départ passé",
            "outcome": {"label": "Départ terminé"},
            "links": {"detail": "/spaces/example/retrieval/occurrences/past-one/"},
        }]
        groups = group_retrieval_rows(
            rows, history=True,
            context={"q": "Départ", "page": 3, "from": "2026-09-01",
                     "kind": "occurrence", "responsibility": "all"},
        )
        self.assertEqual(groups[0]["label"], "Départ terminé")
        url = groups[0]["items"][0]["web_destination"]
        self.assertIn("from=2026-09-01", url)
        self.assertIn("page=3", url)
        self.assertIn("selected=occurrence%3Apast-one", url)

    def test_external_destination_is_never_followed(self):
        rows = [{
            "source": {"kind": "activity", "id": "a"},
            "title": "Known",
            "human_type": "Activité",
            "destination": "https://external.example/private",
        }]
        self.assertIsNone(
            group_retrieval_rows(rows)[0]["items"][0]["web_destination"]
        )
