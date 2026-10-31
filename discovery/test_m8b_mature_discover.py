from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from opportunities.models import (
    Opportunity,
    OpportunityKind,
    OpportunityPublicationStatus,
    OpportunityRevision,
    OpportunitySave,
)

from .card_contract import present_opportunity_card
from .candidate_identity import opportunity_candidate_key
from .unified import public_opportunity_discovery_items
from .views import _added_date_label, _discovery_first_person_action_label, _web_discovery_card


User = get_user_model()


class M8BMatureDiscoverTests(TestCase):
    def setUp(self):
        self.now = timezone.now()
        self.owner = User.objects.create_user(
            username="m8b-owner",
            email="m8b-owner@example.test",
            password="StrongPass2026!",
        )
        self.viewer = User.objects.create_user(
            username="m8b-viewer",
            email="m8b-viewer@example.test",
            password="StrongPass2026!",
        )

    def published_opportunity(self, title, *, opens_at=None, deadline_at=None):
        opportunity = Opportunity.objects.create(
            kind=OpportunityKind.SCHOLARSHIP,
            created_by=self.owner,
        )
        revision = OpportunityRevision.objects.create(
            opportunity=opportunity,
            version=1,
            title=title,
            summary=f"Résumé {title}",
            issuer_name="Fondation M8-B",
            opens_at=opens_at,
            deadline_at=deadline_at,
            timezone="Africa/Lubumbashi",
            created_by=self.owner,
        )
        OpportunityRevision.objects.filter(pk=revision.pk).update(published_at=self.now)
        Opportunity.objects.filter(pk=opportunity.pk).update(
            current_revision=revision,
            publication_status=OpportunityPublicationStatus.PUBLISHED,
            published_at=self.now,
        )
        opportunity.refresh_from_db()
        revision.refresh_from_db()
        return opportunity, revision

    def test_open_opportunity_uses_universal_card_without_fake_activity(self):
        opportunity, _ = self.published_opportunity(
            "Bourse universelle M8-B",
            opens_at=self.now - timedelta(days=1),
            deadline_at=self.now + timedelta(days=10),
        )
        item = public_opportunity_discovery_items(
            {"q": "Bourse universelle M8-B"},
            now=self.now,
        )[0]

        card = present_opportunity_card(item)

        self.assertEqual(card.candidate_key, str(opportunity_candidate_key(opportunity)))
        self.assertEqual(card.presentation_kind, "opportunity")
        self.assertIsNone(card.activity_id)
        self.assertIsNone(card.occurrence_id)
        self.assertIsNone(card.participant_state)
        self.assertEqual(card.actions.primary.url, reverse("opportunities:detail", args=[opportunity.pk]))
        self.assertEqual(card.actions.save.url, reverse("opportunities:save-toggle", args=[opportunity.pk]))
        self.assertEqual(card.actions.share.url, reverse("sharing:create-opportunity", args=[opportunity.pk]))
        self.assertEqual(card.representation.kind, "opportunity")
        self.assertIsNone(card.representation.image_url)

    def test_upcoming_opportunity_is_informative_not_actionable_now(self):
        opportunity, _ = self.published_opportunity(
            "Bourse future M8-B",
            opens_at=self.now + timedelta(days=3),
            deadline_at=self.now + timedelta(days=20),
        )
        item = public_opportunity_discovery_items(
            {"q": "Bourse future M8-B"},
            now=self.now,
        )[0]

        card = present_opportunity_card(item)

        self.assertEqual(card.candidate_key, str(opportunity_candidate_key(opportunity)))
        self.assertIsNone(card.actions.primary)
        state_fact = next(fact for fact in card.facts if fact.code == "state")
        self.assertEqual(state_fact.value, "À venir")

    def test_discover_renders_opportunity_through_universal_card_contract(self):
        opportunity, _ = self.published_opportunity(
            "Bourse carte M8-B",
            opens_at=self.now - timedelta(days=1),
            deadline_at=self.now + timedelta(days=10),
        )

        response = self.client.get(reverse("discovery:home"), {"q": "Bourse carte M8-B"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["discovery_cards"]), 1)
        card = response.context["discovery_cards"][0]
        self.assertEqual(card.candidate_key, str(opportunity_candidate_key(opportunity)))
        self.assertContains(response, f'data-candidate-key="opportunity:{opportunity.pk}"')
        self.assertContains(response, "Opportunité")
        self.assertNotContains(response, ">Opportunity<")
        self.assertContains(response, reverse("core:login"))
        self.assertNotContains(response, reverse("discovery:activity-bookmark-toggle", args=[opportunity.pk]))
        self.assertContains(response, "Vous avez vu ce qui est pertinent ici.")
        self.assertContains(response, "Makolo ne relâche pas vos critères en silence.")
        self.assertEqual(response.context["map_items"], [])
        self.assertEqual(response.context["mappable_result_count"], 0)

    def test_authenticated_opportunity_save_state_uses_canonical_opportunity_save(self):
        opportunity, _ = self.published_opportunity(
            "Bourse enregistrée M8-B",
            opens_at=self.now - timedelta(days=1),
            deadline_at=self.now + timedelta(days=10),
        )
        OpportunitySave.objects.create(profile=self.viewer, opportunity=opportunity)
        self.client.force_login(self.viewer)

        response = self.client.get(reverse("discovery:home"), {"q": "Bourse enregistrée M8-B"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("opportunities:save-toggle", args=[opportunity.pk]))
        self.assertContains(response, reverse("sharing:create-opportunity", args=[opportunity.pk]))
        self.assertContains(response, 'aria-pressed="true"')
        self.assertContains(response, "Enregistré")

    def test_n1_action_row_uses_three_positions_and_existing_share_options(self):
        opportunity, _ = self.published_opportunity(
            "Bourse N1 complète",
            opens_at=self.now - timedelta(days=1),
            deadline_at=self.now + timedelta(days=10),
        )
        self.client.force_login(self.viewer)

        response = self.client.get(reverse("discovery:home"), {"q": "Bourse N1 complète"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["discovery_cards"]), 1)
        self.assertContains(response, 'aria-label="Interactions avec cette possibilité"')
        self.assertContains(response, "J’enregistre")
        self.assertContains(response, reverse("opportunities:save-toggle", args=[opportunity.pk]))
        self.assertContains(response, "data-share-internal")
        self.assertContains(response, "data-share-person-search")
        self.assertContains(response, "data-share-native")
        self.assertContains(response, "data-share-copy")
        self.assertContains(response, "data-share-qr-button")
        self.assertNotContains(response, "mk-discovery-preview-action")

    def test_n1_web_actions_preserve_distinct_web_and_api_authority(self):
        projection = {
            "identity": {
                "family": "service_activity",
                "candidate_key": "service_activity:example",
                "resource": {"kind": "activity", "id": "example"},
                "occurrence": None,
            },
            "representation": {
                "title": "Atelier de formation",
                "summary": "Atelier",
                "kind": "service",
            },
            "owner": {"display_name": "Organisateur"},
            "saved": {"state": "not_saved"},
            "capabilities": ["save"],
            "links": {"web": "/atelier/", "detail": "/api/detail/"},
            "engagement": {
                "presentation": {
                    "label": "S'inscrire",
                    "capability": "start",
                    "enabled": False,
                    "web_enabled": True,
                    "web": "/inscription/",
                },
            },
        }

        card = _web_discovery_card(projection)
        self.assertIsNone(card.actions.save)
        self.assertIsNotNone(card.actions.primary)
        self.assertTrue(card.actions.primary.enabled)
        self.assertEqual(card.actions.primary.label, "Je m'inscris")
        self.assertEqual(card.actions.primary.url, "/inscription/")
        self.assertEqual(_discovery_first_person_action_label("Payer"), "Je paye")
        self.assertEqual(_discovery_first_person_action_label("Voir mon billet"), "Voir mon billet")

        projection["engagement"]["presentation"]["web_enabled"] = False
        self.assertFalse(_web_discovery_card(projection).actions.primary.enabled)

    def test_discovery_cards_follow_the_common_paginated_candidate_sequence(self):
        first, _ = self.published_opportunity(
            "Séquence M8-B alpha",
            opens_at=self.now - timedelta(days=1),
            deadline_at=self.now + timedelta(days=10),
        )
        second, _ = self.published_opportunity(
            "Séquence M8-B beta",
            opens_at=self.now - timedelta(days=1),
            deadline_at=self.now + timedelta(days=11),
        )

        response = self.client.get(reverse("discovery:home"), {"q": "Séquence M8-B"})

        page_keys = [key for _, key, _ in response.context["page_obj"].object_list]
        card_keys = [card.candidate_key for card in response.context["discovery_cards"]]
        self.assertEqual(card_keys, page_keys)
        self.assertEqual(
            set(card_keys),
            {str(opportunity_candidate_key(first)), str(opportunity_candidate_key(second))},
        )

    def test_closed_opportunity_is_not_promoted_as_available_discover_card(self):
        self.published_opportunity(
            "Bourse fermée M8-B",
            opens_at=self.now - timedelta(days=10),
            deadline_at=self.now - timedelta(days=1),
        )

        response = self.client.get(reverse("discovery:home"), {"q": "Bourse fermée M8-B"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["discovery_cards"], [])
        self.assertContains(response, "Aucune possibilité ne correspond à cette recherche.")

    def test_n1_human_added_at_is_distinct_from_owner_event_timing(self):
        local_zone = timezone.get_current_timezone()
        now = timezone.make_aware(datetime(2026, 10, 31, 14, 0), local_zone)
        self.assertEqual(
            _added_date_label((now - timedelta(hours=2)).isoformat(), now=now),
            "il y a 2 h",
        )
        self.assertEqual(
            _added_date_label((now - timedelta(days=1)).isoformat(), now=now),
            "Hier",
        )
        self.assertEqual(
            _added_date_label((now - timedelta(days=14)).isoformat(), now=now),
            "il y a 2 sem.",
        )
        self.assertEqual(_added_date_label("not-a-date", now=now), "")
        self.assertEqual(
            _added_date_label((now + timedelta(days=1)).isoformat(), now=now),
            "01/11/2026",
        )

    def test_n1_web_practical_roles_classification_and_known_unavailability(self):
        projection = {
            "identity": {
                "family": "activity",
                "candidate_key": "activity:transport",
                "resource": {"kind": "activity", "id": "transport"},
                "occurrence": None,
            },
            "representation": {
                "title": "Transport Lubumbashi – Kolwezi",
                "summary": "Un départ connu.",
                "kind": "route",
                "vertical_label": "Transport",
                "eyebrow": "Transport",
            },
            "presentation_facts": [
                {"code": "type", "label": "Type", "value": "Transport"},
            ],
            "availability": {"state": "sold_out"},
            "spatial_facts": [
                {"role": "departure", "place": {"name": "Lubumbashi"}},
                {"role": "stopover", "place": {"name": "Likasi"}},
                {"role": "stopover", "place": {"name": "Fungurume"}},
                {"role": "arrival", "place": {"name": "Kolwezi"}},
            ],
            "temporal_facts": [
                {"kind": "deadline_at", "value": "2026-11-01T12:00:00+02:00"},
            ],
            "date": {"kind": "added_at", "value": "2026-10-30T12:00:00+02:00"},
            "links": {"web": "/transport/"},
        }
        card = _web_discovery_card(projection)
        self.assertEqual(card.type_labels, ("Transport",))
        self.assertFalse(any(fact.label == "Type" for fact in card.facts))
        by_label = {fact.label: fact.value for fact in card.facts}
        self.assertEqual(by_label["Disponibilité"], "Complet")
        self.assertEqual(by_label["Départ"], "Lubumbashi")
        self.assertEqual(by_label["Escale 1"], "Likasi")
        self.assertEqual(by_label["Escale 2"], "Fungurume")
        self.assertEqual(by_label["Arrivée"], "Kolwezi")
        self.assertIn("Date limite", by_label)
        self.assertTrue(card.added_label)
        self.assertNotEqual(card.added_label, by_label["Date limite"])
