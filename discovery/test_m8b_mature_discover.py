from datetime import timedelta

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
