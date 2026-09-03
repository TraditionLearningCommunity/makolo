from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from activities.models import Activity
from authorization.constants import SystemRoleCode
from authorization.services import grant_space_role
from journeys.models import Journey, JourneyBlocker, JourneyStatus, WorkflowKind
from organizations.models import Organization, Team, TeamMembership

from .forms import DossierLifecycleForm
from .models import (
    DossierJourneyDependency,
    DossierJourneyDependencyState,
    DossierJourneyLink,
    DossierLifecycle,
)
from .selectors import visible_dependencies_for_profile, visible_linked_journeys
from .services import (
    add_dependency,
    create_dossier,
    dependency_is_satisfied,
    link_journey,
    remove_dependency,
    set_dossier_lifecycle,
    unlink_journey,
    waive_dependency,
)


User = get_user_model()


class D1DossierFoundationTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="d1-owner", email="d1-owner@example.test", password="StrongPass2026!")
        self.other = User.objects.create_user(username="d1-other", email="d1-other@example.test", password="StrongPass2026!")
        self.activity = Activity.objects.create(owner_profile=self.owner, created_by=self.owner, title="Démarche D1")
        self.private_activity = Activity.objects.create(owner_profile=self.other, created_by=self.other, title="Démarche privée")
        self.journey = Journey.objects.create(
            initiated_by=self.owner,
            beneficiary=self.owner,
            activity=self.activity,
            workflow=WorkflowKind.SERVICE,
            status=JourneyStatus.DRAFT,
        )
        self.private_journey = Journey.objects.create(
            initiated_by=self.other,
            beneficiary=self.other,
            activity=self.private_activity,
            workflow=WorkflowKind.SERVICE,
            status=JourneyStatus.DRAFT,
        )

    def test_personal_dossier_link_unlink_history_and_legacy_journey(self):
        dossier = create_dossier(actor=self.owner, owner_profile=self.owner, title="Obtenir la bourse")
        link = link_journey(actor=self.owner, dossier=dossier, journey=self.journey)
        self.assertEqual(link_journey(actor=self.owner, dossier=dossier, journey=self.journey).pk, link.pk)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                DossierJourneyLink.objects.create(dossier=dossier, journey=self.journey, linked_by=self.owner)
        unlink_journey(actor=self.owner, dossier=dossier, journey=self.journey)
        link.refresh_from_db()
        self.assertFalse(link.is_active)
        self.assertEqual(link.unlinked_by, self.owner)
        self.assertTrue(Journey.objects.filter(pk=self.journey.pk).exists())
        self.assertEqual(DossierJourneyLink.objects.filter(pk=link.pk).count(), 1)
        self.assertTrue(Journey.objects.filter(pk=self.private_journey.pk, dossier_links__isnull=True).exists())

    def test_space_dossier_requires_mandate_membership_alone_is_not_authority(self):
        space = Organization.objects.create(name="Espace D1", created_by=self.owner)
        member = User.objects.create_user(username="d1-member", email="d1-member@example.test", password="StrongPass2026!")
        team = Team.objects.create(organization=space, name="Équipe D1", is_default=True)
        TeamMembership.objects.create(team=team, user=member)
        with self.assertRaises(PermissionDenied):
            create_dossier(actor=member, owning_space=space, title="Interdit")
        grant_space_role(profile=self.owner, space=space, role=SystemRoleCode.SPACE_ADMIN, granted_by=self.owner)
        dossier = create_dossier(actor=self.owner, owning_space=space, title="Dossier Espace")
        self.assertEqual(dossier.owning_space, space)
        self.assertIsNone(dossier.owner_profile_id)

    def test_dossier_right_never_grants_private_journey_right(self):
        dossier = create_dossier(actor=self.owner, owner_profile=self.owner, title="Dossier privé")
        with self.assertRaises(PermissionDenied):
            link_journey(actor=self.owner, dossier=dossier, journey=self.private_journey)
        DossierJourneyLink.objects.create(dossier=dossier, journey=self.private_journey, linked_by=self.other)
        self.assertEqual(list(visible_linked_journeys(self.owner, dossier)), [])

    def test_unauthorized_uuid_is_404(self):
        dossier = create_dossier(actor=self.owner, owner_profile=self.owner, title="Secret")
        self.client.force_login(self.other)
        response = self.client.get(reverse("objectives:dossier-detail", args=[dossier.pk]))
        self.assertEqual(response.status_code, 404)

    def test_archive_dossier_does_not_change_journey_lifecycle(self):
        dossier = create_dossier(actor=self.owner, owner_profile=self.owner, title="Archive")
        link_journey(actor=self.owner, dossier=dossier, journey=self.journey)
        original_status = self.journey.status
        set_dossier_lifecycle(actor=self.owner, dossier=dossier, lifecycle=DossierLifecycle.ARCHIVED)
        self.journey.refresh_from_db()
        self.assertEqual(self.journey.status, original_status)
        self.assertTrue(Journey.objects.filter(pk=self.journey.pk).exists())

    def test_link_form_does_not_offer_private_journey(self):
        dossier = create_dossier(actor=self.owner, owner_profile=self.owner, title="UI")
        self.client.force_login(self.owner)
        response = self.client.get(reverse("objectives:dossier-detail", args=[dossier.pk]))
        self.assertContains(response, self.activity.title)
        self.assertNotContains(response, self.private_activity.title)

    def test_lifecycle_form_rejects_transition_outside_service_graph(self):
        dossier = create_dossier(actor=self.owner, owner_profile=self.owner, title="Lifecycle")
        dossier = set_dossier_lifecycle(actor=self.owner, dossier=dossier, lifecycle=DossierLifecycle.ARCHIVED)
        form = DossierLifecycleForm({"lifecycle": DossierLifecycle.ACTIVE}, dossier=dossier)
        self.assertFalse(form.is_valid())


class D2CrossJourneyDependencyTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="d2-owner", email="d2-owner@example.test", password="StrongPass2026!")
        self.other = User.objects.create_user(username="d2-other", email="d2-other@example.test", password="StrongPass2026!")
        self.dossier = create_dossier(actor=self.owner, owner_profile=self.owner, title="Obtenir la bourse de Junior")
        self.links = {}
        for key, title in [("a", "Déposer la candidature"), ("b", "Récupérer le diplôme"), ("c", "Régulariser les frais"), ("d", "Obtenir la recommandation")]:
            activity = Activity.objects.create(owner_profile=self.owner, created_by=self.owner, title=title)
            journey = Journey.objects.create(
                initiated_by=self.owner,
                beneficiary=self.owner,
                activity=activity,
                workflow=WorkflowKind.SERVICE,
                status=JourneyStatus.DRAFT,
            )
            self.links[key] = link_journey(actor=self.owner, dossier=self.dossier, journey=journey)

    def test_valid_dependency_self_cross_dossier_duplicate_and_cycle_invariants(self):
        dep_ab = add_dependency(actor=self.owner, dossier=self.dossier, dependent_link=self.links["a"], required_link=self.links["b"])
        self.assertEqual(dep_ab.state, DossierJourneyDependencyState.ACTIVE)
        with self.assertRaises(ValidationError):
            add_dependency(actor=self.owner, dossier=self.dossier, dependent_link=self.links["a"], required_link=self.links["a"])
        with self.assertRaises(ValidationError):
            add_dependency(actor=self.owner, dossier=self.dossier, dependent_link=self.links["a"], required_link=self.links["b"])
        other_dossier = create_dossier(actor=self.owner, owner_profile=self.owner, title="Autre objectif")
        other_activity = Activity.objects.create(owner_profile=self.owner, created_by=self.owner, title="Autre démarche")
        other_journey = Journey.objects.create(initiated_by=self.owner, beneficiary=self.owner, activity=other_activity, workflow=WorkflowKind.SERVICE, status=JourneyStatus.DRAFT)
        other_link = link_journey(actor=self.owner, dossier=other_dossier, journey=other_journey)
        with self.assertRaises(ValidationError):
            add_dependency(actor=self.owner, dossier=self.dossier, dependent_link=self.links["a"], required_link=other_link)
        add_dependency(actor=self.owner, dossier=self.dossier, dependent_link=self.links["b"], required_link=self.links["c"])
        with self.assertRaises(ValidationError):
            add_dependency(actor=self.owner, dossier=self.dossier, dependent_link=self.links["c"], required_link=self.links["a"])

    def test_inactive_endpoint_and_active_dependency_protect_unlink_then_waiver_releases_it(self):
        unlink_journey(actor=self.owner, dossier=self.dossier, journey=self.links["d"].journey)
        with self.assertRaises(ValidationError):
            add_dependency(actor=self.owner, dossier=self.dossier, dependent_link=self.links["a"], required_link=self.links["d"])
        dependency = add_dependency(actor=self.owner, dossier=self.dossier, dependent_link=self.links["a"], required_link=self.links["b"])
        with self.assertRaises(ValidationError):
            unlink_journey(actor=self.owner, dossier=self.dossier, journey=self.links["b"].journey)
        waived = waive_dependency(actor=self.owner, dossier=self.dossier, dependency=dependency, reason="Diplôme vérifié hors procédure.")
        self.assertEqual(waived.state, DossierJourneyDependencyState.WAIVED)
        self.assertIsNotNone(waived.closed_at)
        self.assertEqual(waived.closed_by, self.owner)
        unlink_journey(actor=self.owner, dossier=self.dossier, journey=self.links["b"].journey)
        self.links["b"].refresh_from_db()
        self.assertFalse(self.links["b"].is_active)

    def test_remove_keeps_history_and_allows_same_pair_to_be_created_again(self):
        dependency = add_dependency(actor=self.owner, dossier=self.dossier, dependent_link=self.links["a"], required_link=self.links["b"])
        removed = remove_dependency(actor=self.owner, dossier=self.dossier, dependency=dependency)
        self.assertEqual(removed.state, DossierJourneyDependencyState.REMOVED)
        self.assertTrue(DossierJourneyDependency.objects.filter(pk=dependency.pk).exists())
        replacement = add_dependency(actor=self.owner, dossier=self.dossier, dependent_link=self.links["a"], required_link=self.links["b"])
        self.assertNotEqual(replacement.pk, dependency.pk)

    def test_authority_is_required_for_dossier_and_for_both_journeys(self):
        with self.assertRaises(PermissionDenied):
            add_dependency(actor=self.other, dossier=self.dossier, dependent_link=self.links["a"], required_link=self.links["b"])
        private_activity = Activity.objects.create(owner_profile=self.other, created_by=self.other, title="Démarche privée D2")
        private_journey = Journey.objects.create(initiated_by=self.other, beneficiary=self.other, activity=private_activity, workflow=WorkflowKind.SERVICE, status=JourneyStatus.DRAFT)
        private_link = DossierJourneyLink.objects.create(dossier=self.dossier, journey=private_journey, linked_by=self.other)
        with self.assertRaises(PermissionDenied):
            add_dependency(actor=self.owner, dossier=self.dossier, dependent_link=self.links["a"], required_link=private_link)

    def test_hidden_endpoint_omits_dependency_and_known_uuid_cannot_remove_it(self):
        private_activity = Activity.objects.create(owner_profile=self.other, created_by=self.other, title="Secret D2")
        private_journey = Journey.objects.create(initiated_by=self.other, beneficiary=self.other, activity=private_activity, workflow=WorkflowKind.SERVICE, status=JourneyStatus.DRAFT)
        private_link = DossierJourneyLink.objects.create(dossier=self.dossier, journey=private_journey, linked_by=self.other)
        dependency = DossierJourneyDependency.objects.create(dossier=self.dossier, dependent_link=self.links["a"], required_link=private_link, created_by=self.other)
        self.assertEqual(list(visible_dependencies_for_profile(self.owner, self.dossier)), [])
        self.client.force_login(self.owner)
        response = self.client.post(reverse("objectives:dossier-remove-dependency", args=[self.dossier.pk, dependency.pk]))
        self.assertEqual(response.status_code, 404)
        dependency.refresh_from_db()
        self.assertEqual(dependency.state, DossierJourneyDependencyState.ACTIVE)

    def test_fulfilled_is_the_only_automatic_satisfaction_rule(self):
        dependency = add_dependency(actor=self.owner, dossier=self.dossier, dependent_link=self.links["a"], required_link=self.links["b"])
        self.assertFalse(dependency_is_satisfied(dependency))
        Journey.objects.filter(pk=self.links["b"].journey_id).update(status=JourneyStatus.CANCELLED)
        dependency.required_link.journey.refresh_from_db()
        self.assertFalse(dependency_is_satisfied(dependency))
        Journey.objects.filter(pk=self.links["b"].journey_id).update(status=JourneyStatus.FULFILLED)
        dependency.required_link.journey.refresh_from_db()
        self.assertTrue(dependency_is_satisfied(dependency))

    def test_completion_is_gated_only_by_active_unsatisfied_dependencies(self):
        add_dependency(actor=self.owner, dossier=self.dossier, dependent_link=self.links["a"], required_link=self.links["b"])
        dossier = set_dossier_lifecycle(actor=self.owner, dossier=self.dossier, lifecycle=DossierLifecycle.ACTIVE)
        with self.assertRaises(ValidationError):
            set_dossier_lifecycle(actor=self.owner, dossier=dossier, lifecycle=DossierLifecycle.COMPLETED)
        Journey.objects.filter(pk=self.links["b"].journey_id).update(status=JourneyStatus.FULFILLED)
        completed = set_dossier_lifecycle(actor=self.owner, dossier=dossier, lifecycle=DossierLifecycle.COMPLETED)
        self.assertEqual(completed.lifecycle, DossierLifecycle.COMPLETED)
        self.assertEqual(self.links["c"].journey.status, JourneyStatus.DRAFT)
        second_dossier = create_dossier(actor=self.owner, owner_profile=self.owner, title="Waiver completion")
        links = []
        for title in ["Étape autonome A", "Étape autonome B"]:
            activity = Activity.objects.create(owner_profile=self.owner, created_by=self.owner, title=title)
            journey = Journey.objects.create(initiated_by=self.owner, beneficiary=self.owner, activity=activity, workflow=WorkflowKind.SERVICE, status=JourneyStatus.DRAFT)
            links.append(link_journey(actor=self.owner, dossier=second_dossier, journey=journey))
        dependency = add_dependency(actor=self.owner, dossier=second_dossier, dependent_link=links[0], required_link=links[1])
        waive_dependency(actor=self.owner, dossier=second_dossier, dependency=dependency, reason="Décision explicite du coordinateur.")
        second_dossier = set_dossier_lifecycle(actor=self.owner, dossier=second_dossier, lifecycle=DossierLifecycle.ACTIVE)
        second_dossier = set_dossier_lifecycle(actor=self.owner, dossier=second_dossier, lifecycle=DossierLifecycle.COMPLETED)
        self.assertEqual(second_dossier.lifecycle, DossierLifecycle.COMPLETED)

    def test_dependency_mutations_do_not_change_journey_status_or_create_blocker(self):
        initial_statuses = {self.links["a"].journey_id: self.links["a"].journey.status, self.links["b"].journey_id: self.links["b"].journey.status}
        blocker_count = JourneyBlocker.objects.count()
        dependency = add_dependency(actor=self.owner, dossier=self.dossier, dependent_link=self.links["a"], required_link=self.links["b"])
        waive_dependency(actor=self.owner, dossier=self.dossier, dependency=dependency, reason="Décision Dossier.")
        for journey_id, expected_status in initial_statuses.items():
            self.assertEqual(Journey.objects.get(pk=journey_id).status, expected_status)
        self.assertEqual(JourneyBlocker.objects.count(), blocker_count)
