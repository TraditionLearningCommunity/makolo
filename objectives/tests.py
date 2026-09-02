from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from activities.models import Activity
from authorization.constants import SystemRoleCode
from authorization.services import grant_space_role
from journeys.models import Journey, JourneyStatus, WorkflowKind
from organizations.models import Organization, OrganizationMembership

from .forms import DossierLifecycleForm
from .models import DossierJourneyLink, DossierLifecycle
from .selectors import visible_linked_journeys
from .services import create_dossier, link_journey, set_dossier_lifecycle, unlink_journey


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
        OrganizationMembership.objects.create(organization=space, user=member, role="admin")
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
        set_dossier_lifecycle(actor=self.owner, dossier=dossier, lifecycle=DossierLifecycle.ARCHIVED)
        form = DossierLifecycleForm({"lifecycle": DossierLifecycle.ACTIVE}, dossier=dossier)
        self.assertFalse(form.is_valid())
