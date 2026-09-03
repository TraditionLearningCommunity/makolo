from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from activities.models import Activity
from journeys.models import Journey, JourneyStatus, WorkflowKind
from readiness.types import NextAction, ReadinessResult, ReadinessStatus

from .models import DossierJourneyDependency, DossierJourneyLink, DossierLifecycle
from .readiness import HIDDEN_COLLECTIVE_SIGNAL, resolve_dossier_readiness
from .services import add_dependency, create_dossier, link_journey, set_dossier_lifecycle


User = get_user_model()


def readiness(status, action=None):
    from django.utils import timezone
    return ReadinessResult(status=status, checks=(), next_action=action, observed_at=timezone.now())


class D4CollectiveReadinessTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="d4-owner", password="StrongPass2026!")
        self.other = User.objects.create_user(username="d4-other", password="StrongPass2026!")
        self.dossier = create_dossier(actor=self.owner, owner_profile=self.owner, title="Obtenir la bourse de Junior")

    def make_link(self, title, *, actor=None, beneficiary=None, status=JourneyStatus.DRAFT):
        actor = actor or self.owner
        beneficiary = beneficiary or actor
        activity = Activity.objects.create(owner_profile=actor, created_by=actor, title=title)
        journey = Journey.objects.create(initiated_by=actor, beneficiary=beneficiary, activity=activity, workflow=WorkflowKind.SERVICE, status=status)
        return DossierJourneyLink.objects.create(dossier=self.dossier, journey=journey, linked_by=actor)

    def test_collective_priority_and_dependency_satisfaction_without_journey_mutation(self):
        a = self.make_link("A"); b = self.make_link("B")
        dependency = add_dependency(actor=self.owner, dossier=self.dossier, dependent_link=a, required_link=b)
        statuses = {a.journey_id: ReadinessStatus.ACTION_REQUIRED, b.journey_id: ReadinessStatus.WAITING}
        with patch("objectives.readiness.resolve_journey_readiness", side_effect=lambda journey, viewer=None: readiness(statuses[journey.pk])):
            result = resolve_dossier_readiness(self.dossier, viewer=self.owner)
        self.assertEqual(result.status, ReadinessStatus.BLOCKED)
        a.journey.refresh_from_db(); self.assertEqual(a.journey.status, JourneyStatus.DRAFT); self.assertFalse(a.journey.blockers.exists())
        Journey.objects.filter(pk=b.journey_id).update(status=JourneyStatus.FULFILLED)
        with patch("objectives.readiness.resolve_journey_readiness", side_effect=lambda journey, viewer=None: readiness(statuses[journey.pk])):
            self.assertEqual(resolve_dossier_readiness(self.dossier, viewer=self.owner).status, ReadinessStatus.ACTION_REQUIRED)
        statuses[a.journey_id] = ReadinessStatus.READY
        with patch("objectives.readiness.resolve_journey_readiness", side_effect=lambda journey, viewer=None: readiness(statuses[journey.pk])):
            self.assertEqual(resolve_dossier_readiness(self.dossier, viewer=self.owner).status, ReadinessStatus.WAITING)
        self.assertTrue(DossierJourneyDependency.objects.filter(pk=dependency.pk).exists())

    def test_hidden_prerequisite_redacts_identity_and_action(self):
        visible = self.make_link("Déposer la candidature")
        hidden = self.make_link("SECRET DIPLOME", actor=self.other, beneficiary=self.other)
        DossierJourneyDependency.objects.create(dossier=self.dossier, dependent_link=visible, required_link=hidden, created_by=self.other)
        secret_action = NextAction(key="secret", label="SECRET ACTION", url="/secret/url")
        with patch("objectives.readiness.resolve_journey_readiness", side_effect=lambda journey, viewer=None: readiness(ReadinessStatus.ACTION_REQUIRED, secret_action if journey.pk == hidden.journey_id else None)):
            result = resolve_dossier_readiness(self.dossier, viewer=self.owner)
        self.assertEqual(result.status, ReadinessStatus.BLOCKED); self.assertTrue(result.is_partial); self.assertEqual(result.hidden_signal, HIDDEN_COLLECTIVE_SIGNAL)
        rendered = repr(result)
        self.assertNotIn(str(hidden.journey_id), rendered); self.assertNotIn("SECRET DIPLOME", rendered); self.assertNotIn("SECRET ACTION", rendered); self.assertNotIn("/secret/url", rendered)
        self.assertTrue(result.visible_items[0].hidden_dependency); self.assertIsNone(result.primary_next_action)

    def test_fully_hidden_blocker_only_emits_collective_sentinel(self):
        hidden = self.make_link("SECRET BLOCKER", actor=self.other, beneficiary=self.other)
        with patch("objectives.readiness.resolve_journey_readiness", return_value=readiness(ReadinessStatus.BLOCKED)):
            result = resolve_dossier_readiness(self.dossier, viewer=self.owner)
        self.assertEqual(result.status, ReadinessStatus.BLOCKED); self.assertTrue(result.is_partial)
        self.assertEqual(result.visible_items, ()); self.assertEqual(result.visible_dependencies, ()); self.assertEqual(result.hidden_signal, HIDDEN_COLLECTIVE_SIGNAL)
        self.assertNotIn(str(hidden.journey_id), repr(result)); self.assertNotIn("SECRET BLOCKER", repr(result))

    def test_visible_prerequisite_action_is_primary_then_disappears_when_hidden(self):
        dependent = self.make_link("Candidature"); required = self.make_link("Diplôme")
        add_dependency(actor=self.owner, dossier=self.dossier, dependent_link=dependent, required_link=required)
        action = NextAction(key="continue", label="Continuer cette démarche", url="/journeys/continue")
        with patch("objectives.readiness.resolve_journey_readiness", side_effect=lambda journey, viewer=None: readiness(ReadinessStatus.ACTION_REQUIRED if journey.pk == required.journey_id else ReadinessStatus.READY, action if journey.pk == required.journey_id else None)):
            result = resolve_dossier_readiness(self.dossier, viewer=self.owner)
        self.assertEqual(result.primary_next_action.label, "Continuer cette démarche")
        Journey.objects.filter(pk=required.journey_id).update(initiated_by=self.other, beneficiary=self.other)
        with patch("objectives.readiness.resolve_journey_readiness", side_effect=lambda journey, viewer=None: readiness(ReadinessStatus.ACTION_REQUIRED if journey.pk == required.journey_id else ReadinessStatus.READY, action if journey.pk == required.journey_id else None)):
            hidden_result = resolve_dossier_readiness(self.dossier, viewer=self.owner)
        self.assertIsNone(hidden_result.primary_next_action); self.assertTrue(hidden_result.is_partial)

    def test_visible_journey_action_is_not_exposed_to_non_beneficiary_collaborator(self):
        link = self.make_link("Visible mais action participant")
        action = NextAction(key="complete_form", label="Compléter formulaire", url="/questionnaires/requests/private/")
        with patch("objectives.readiness.resolve_journey_readiness", return_value=readiness(ReadinessStatus.ACTION_REQUIRED, action)):
            owner_result = resolve_dossier_readiness(self.dossier, viewer=self.owner)
        self.assertIsNotNone(owner_result.primary_next_action)
        Journey.objects.filter(pk=link.journey_id).update(beneficiary=self.other)
        with patch("objectives.readiness.resolve_journey_readiness", return_value=readiness(ReadinessStatus.ACTION_REQUIRED, action)):
            collaborator_result = resolve_dossier_readiness(self.dossier, viewer=self.owner)
        self.assertIsNone(collaborator_result.primary_next_action)

    def test_terminal_lifecycle_semantics(self):
        completed = set_dossier_lifecycle(actor=self.owner, dossier=self.dossier, lifecycle=DossierLifecycle.ACTIVE)
        completed = set_dossier_lifecycle(actor=self.owner, dossier=completed, lifecycle=DossierLifecycle.COMPLETED)
        self.assertEqual(resolve_dossier_readiness(completed, viewer=self.owner).status, ReadinessStatus.COMPLETE)
        self.assertIsNone(resolve_dossier_readiness(completed, viewer=self.owner).primary_next_action)
        cancelled = create_dossier(actor=self.owner, owner_profile=self.owner, title="Cancelled")
        cancelled = set_dossier_lifecycle(actor=self.owner, dossier=cancelled, lifecycle=DossierLifecycle.CANCELLED)
        self.assertIsNone(resolve_dossier_readiness(cancelled, viewer=self.owner).status)
        archived = create_dossier(actor=self.owner, owner_profile=self.owner, title="Archived")
        archived = set_dossier_lifecycle(actor=self.owner, dossier=archived, lifecycle=DossierLifecycle.ARCHIVED)
        self.assertIsNone(resolve_dossier_readiness(archived, viewer=self.owner).status)

    def test_query_growth_is_bounded_for_multiple_journeys(self):
        for index in range(2): self.make_link(f"Petite démarche {index}")
        with CaptureQueriesContext(connection) as small:
            resolve_dossier_readiness(self.dossier, viewer=self.owner)
        for index in range(4): self.make_link(f"Démarche supplémentaire {index}")
        with CaptureQueriesContext(connection) as larger:
            resolve_dossier_readiness(self.dossier, viewer=self.owner)
        self.assertLessEqual(len(larger), len(small) + 2)
