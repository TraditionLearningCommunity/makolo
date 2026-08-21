from types import SimpleNamespace

from django.test import SimpleTestCase

from commerce.models import PaymentMode
from journeys.models import WorkflowKind

from .product_language import payment_mode_label, vocabulary_for, vertical_for


class ProductLanguageTests(SimpleTestCase):
    def setUp(self):
        self.generic = SimpleNamespace()
        self.event = SimpleNamespace(event_vertical=object())
        self.transport = SimpleNamespace(transport_service=object())

    def test_generic_fallback_does_not_require_commerce(self):
        vocabulary = vocabulary_for(activity=self.generic)
        self.assertEqual(vertical_for(self.generic), "generic")
        self.assertEqual(vocabulary.activity_noun, "Activité")
        self.assertEqual(vocabulary.journey_noun, "Démarche")
        self.assertEqual(vocabulary.offer_noun, "Tarif")
        self.assertEqual(vocabulary.access_noun, "Accès")

    def test_event_free_registration_language(self):
        vocabulary = vocabulary_for(activity=self.event, workflow=WorkflowKind.REGISTRATION)
        self.assertEqual(vocabulary.activity_noun, "Événement")
        self.assertEqual(vocabulary.journey_noun, "Inscription")
        self.assertEqual(vocabulary.primary_action, "S’inscrire")
        self.assertEqual(vocabulary.access_noun, "Confirmation")

    def test_event_purchase_language(self):
        vocabulary = vocabulary_for(activity=self.event, workflow=WorkflowKind.PURCHASE)
        self.assertEqual(vocabulary.journey_noun, "Achat de billet")
        self.assertEqual(vocabulary.offer_noun, "Type de billet")
        self.assertEqual(vocabulary.access_noun, "Billet")
        self.assertEqual(vocabulary.primary_action, "Acheter le billet")

    def test_event_invitation_is_not_a_commerce_order(self):
        vocabulary = vocabulary_for(activity=self.event, workflow=WorkflowKind.INVITATION)
        self.assertEqual(vocabulary.journey_noun, "Invitation")
        self.assertEqual(vocabulary.access_noun, "Invitation")
        self.assertEqual(vocabulary.primary_action, "Accepter l’invitation")

    def test_transport_language_is_independent_from_event(self):
        vocabulary = vocabulary_for(activity=self.transport, workflow=WorkflowKind.RESERVATION)
        self.assertEqual(vertical_for(self.transport), "transport")
        self.assertEqual(vocabulary.activity_noun, "Trajet")
        self.assertEqual(vocabulary.occurrence_noun, "Départ")
        self.assertEqual(vocabulary.journey_noun, "Réservation")
        self.assertEqual(vocabulary.offer_noun, "Tarif")
        self.assertEqual(vocabulary.access_noun, "Billet")
        self.assertEqual(vocabulary.participant_noun, "Voyageur")
        self.assertEqual(vocabulary.primary_action, "Réserver")

    def test_payment_modes_are_user_facing(self):
        self.assertEqual(payment_mode_label(PaymentMode.NONE), "")
        self.assertEqual(payment_mode_label(PaymentMode.UPFRONT), "Paiement en ligne")
        self.assertEqual(payment_mode_label(PaymentMode.AFTER_APPROVAL), "Paiement après validation")
        self.assertEqual(payment_mode_label(PaymentMode.ON_SITE), "À payer sur place")
        self.assertEqual(payment_mode_label(PaymentMode.LATER), "Paiement ultérieur")
