import uuid
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from activities.models import ActivityStatus, ActivityVisibility, OccurrenceStatus
from activities.services import create_activity, create_occurrence
from core.participant_presentation import ParticipantActivityState
from core.product_language import vocabulary_for
from services.models import OpportunityPolicy, ServiceDetails, ServiceKind

from .card_contract import present_occurrence_card
from .models import ActivityBookmark
from .presentation import DiscoveryAvailability, DiscoveryItem, DiscoveryPlace, DiscoveryPrice


User = get_user_model()


def _participant_state(**overrides):
    values = {
        "availability": "available",
        "availability_label": "Disponible",
        "participant_state": "none",
        "label": None,
        "secondary_label": None,
        "primary_action": "S’inscrire",
        "primary_url": "/agir/",
        "visual_variant": "brand",
        "expires_at": None,
    }
    values.update(overrides)
    return ParticipantActivityState(**values)


def _item(*, participant=None, price=None, availability=None):
    now = timezone.now()
    activity_id = str(uuid.uuid4())
    occurrence_id = str(uuid.uuid4())
    participant = participant or _participant_state()
    return DiscoveryItem(
        activity_id=activity_id,
        occurrence_id=occurrence_id,
        vertical="event",
        vertical_label="Événement",
        title="Kasaï All Stars",
        summary="Une possibilité réelle.",
        space_name="Pullman Lubumbashi",
        start_at=now + timedelta(days=1),
        end_at=now + timedelta(days=1, hours=2),
        timezone="Africa/Lubumbashi",
        local_start=now + timedelta(days=1),
        place=DiscoveryPlace(
            id=str(uuid.uuid4()),
            name="Pullman",
            locality="Lubumbashi",
            latitude=-11.66,
            longitude=27.48,
        ),
        distance_km=3.2,
        price=price or DiscoveryPrice(False, Decimal("20.00"), "USD", "À partir de 20 USD"),
        availability=availability or DiscoveryAvailability("available", "Disponible", 42),
        participant=participant,
        cta_label=participant.primary_action,
        cta_url=participant.primary_url,
        url="/detail/",
        image_url=None,
        eyebrow="Concert",
    )


class DiscoveryCardContractTests(TestCase):
    def test_card_separates_decision_facts_from_actions(self):
        card = present_occurrence_card(_item())
        facts = {fact.code: fact.value for fact in card.facts}
        self.assertEqual(card.presentation_kind, "event")
        self.assertEqual(facts["price"], "À partir de 20 USD")
        self.assertEqual(facts["capacity"], "42 places restantes")
        self.assertEqual(facts["distance"], "3.2 km")
        self.assertEqual(card.actions.save.label, "Enregistrer")
        self.assertEqual(card.actions.primary.label, "Acheter")
        self.assertEqual(card.actions.share.label, "Partager")
        self.assertFalse(any("intéress" in fact.value.lower() for fact in card.facts))

    def test_saved_state_is_private_personal_action_state_without_counter(self):
        card = present_occurrence_card(_item(), bookmarked=True)
        self.assertEqual(card.actions.save.state, "saved")
        self.assertEqual(card.actions.save.label, "Enregistré")
        self.assertNotIn("count", card.actions.save.__dataclass_fields__)

    def test_access_progresses_primary_action_to_my_ticket(self):
        participant = _participant_state(
            participant_state="access_valid",
            label="Vous avez accès",
            primary_action="Voir mon billet",
            primary_url="/mon-billet/",
        )
        card = present_occurrence_card(_item(participant=participant))
        self.assertEqual(card.actions.primary.code, "access")
        self.assertEqual(card.actions.primary.label, "Mon billet")
        self.assertEqual(card.actions.primary.url, "/mon-billet/")

    def test_sold_out_fact_describes_remaining_possibility(self):
        card = present_occurrence_card(
            _item(availability=DiscoveryAvailability("sold_out", "Complet", 0))
        )
        capacity = next(fact for fact in card.facts if fact.code == "capacity")
        self.assertEqual(capacity.value, "Complet")

    def test_terminal_states_disable_primary_action(self):
        for availability in ("cancelled", "completed"):
            with self.subTest(availability=availability):
                participant = _participant_state(
                    availability=availability,
                    availability_label="Indisponible",
                )
                card = present_occurrence_card(_item(participant=participant))
                self.assertFalse(card.actions.primary.enabled)

    def test_map_payload_keeps_participant_state_private(self):
        participant = _participant_state(
            participant_state="payment_pending",
            label="Paiement en attente",
            secondary_label="Information privée",
            primary_action="Reprendre le paiement",
            primary_url="/payer/",
        )
        payload = _item(participant=participant).to_map_dict()
        self.assertNotIn("participant", payload)
        self.assertNotIn("secondary_label", payload)
        self.assertNotIn("Paiement en attente", str(payload))
        self.assertNotIn("Information privée", str(payload))


class DiscoveryPresentationWebTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="presentation-owner",
            email="presentation-owner@example.test",
            password="test-pass",
        )
        self.participant = User.objects.create_user(
            username="presentation-participant",
            email="presentation-participant@example.test",
            password="test-pass",
        )
        self.activity = create_activity(
            created_by=self.owner,
            owner_profile=self.owner,
            title="Atelier universel",
            status=ActivityStatus.PUBLISHED,
            visibility=ActivityVisibility.PUBLIC,
        )
        self.occurrence = create_occurrence(
            activity=self.activity,
            start_at=timezone.now() + timedelta(days=2),
            end_at=timezone.now() + timedelta(days=2, hours=2),
            timezone="Africa/Lubumbashi",
            status=OccurrenceStatus.SCHEDULED,
        )

    def test_unauthenticated_discovery_has_explicit_save_primary_share_fallback(self):
        response = self.client.get(reverse("discovery:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Enregistrer")
        self.assertContains(response, "Partager")
        self.assertContains(response, reverse("core:login"))
        self.assertNotContains(response, "personnes intéressées")
        self.assertNotContains(response, "enregistrements")

    def test_authenticated_bookmark_projects_saved_orbit_state(self):
        ActivityBookmark.objects.create(user=self.participant, activity=self.activity)
        self.client.force_login(self.participant)
        response = self.client.get(reverse("discovery:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Enregistré")
        self.assertContains(response, 'aria-pressed="true"')
        self.assertContains(
            response,
            reverse("discovery:activity-bookmark-toggle", args=[self.activity.pk]),
        )

    def test_bookmark_toggle_saves_then_unsaves_canonical_activity_bookmark(self):
        self.client.force_login(self.participant)
        url = reverse("discovery:activity-bookmark-toggle", args=[self.activity.pk])
        next_url = reverse("discovery:home")
        first = self.client.post(url, {"next": next_url})
        self.assertRedirects(first, next_url)
        self.assertTrue(ActivityBookmark.objects.filter(user=self.participant, activity=self.activity).exists())
        second = self.client.post(url, {"next": next_url})
        self.assertRedirects(second, next_url)
        self.assertFalse(ActivityBookmark.objects.filter(user=self.participant, activity=self.activity).exists())

    def test_home_and_discovery_remain_separate_with_explicit_progressive_navigation(self):
        self.client.force_login(self.participant)
        home = self.client.get(reverse("core:participant-home"))
        discovery = self.client.get(reverse("discovery:home"))
        self.assertEqual(home.status_code, 200)
        self.assertEqual(discovery.status_code, 200)
        self.assertContains(home, "Et maintenant ?")
        self.assertContains(home, reverse("discovery:home"))
        self.assertContains(discovery, "Mon espace")
        self.assertContains(discovery, reverse("core:participant-home"))
        self.assertNotEqual(reverse("core:participant-home"), reverse("discovery:home"))

    def test_service_is_first_class_activity_vocabulary_without_occurrence(self):
        service_activity = create_activity(
            created_by=self.owner,
            owner_profile=self.owner,
            title="Accompagnement candidature",
            status=ActivityStatus.PUBLISHED,
            visibility=ActivityVisibility.PUBLIC,
        )
        ServiceDetails.objects.create(
            activity=service_activity,
            service_kind=ServiceKind.APPLICATION_SUPPORT,
            opportunity_policy=OpportunityPolicy.NONE,
        )
        vocabulary = vocabulary_for(activity=service_activity)
        self.assertEqual(vocabulary.vertical, "service")
        self.assertEqual(vocabulary.primary_action, "Commencer")
        response = self.client.get(reverse("discovery:home"), {"vertical": "service"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Accompagnement candidature")
        self.assertContains(response, "Commencer")
        self.assertContains(
            response,
            reverse("sharing:create-activity", args=[service_activity.pk]),
        )
