from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from access.models import Access, AccessStatus
from access.services import issue_access
from activities.models import Activity, ActivityStatus, Occurrence, OccurrenceStatus
from authorization.constants import PermissionCode, SystemRoleCode
from authorization.models import AuthorityScope, Mandate, Permission, Role, RolePermission
from authorization.services import grant_activity_role, grant_space_role

from .models import Organization, Team, TeamMembership


User = get_user_model()


class ManualAccessGrantConsoleTests(TestCase):
    def setUp(self):
        self.creator = User.objects.create_user(
            username="console-grant-creator",
            email="console-grant-creator@example.com",
        )
        self.owner = User.objects.create_user(
            username="console-grant-owner",
            email="console-grant-owner@example.com",
            password="Console-2026!",
            first_name="Naomi",
            last_name="Kabongo",
        )
        self.local_manager = User.objects.create_user(
            username="console-grant-local",
            email="console-grant-local@example.com",
            password="Console-2026!",
        )
        self.viewer = User.objects.create_user(
            username="console-grant-viewer",
            email="console-grant-viewer@example.com",
            password="Console-2026!",
        )
        self.team_only = User.objects.create_user(
            username="console-grant-team-only",
            email="console-grant-team-only@example.com",
            password="Console-2026!",
        )
        self.beneficiary = User.objects.create_user(
            username="console-grant-beneficiary",
            email="beneficiary.grant@example.com",
            password="Console-2026!",
        )
        self.inactive = User.objects.create_user(
            username="console-grant-inactive",
            email="inactive.grant@example.com",
            password="Console-2026!",
            is_active=False,
        )
        self.space = Organization.objects.create(
            name="Console Grant Space",
            slug="console-grant-space",
            created_by=self.creator,
        )
        self.other_space = Organization.objects.create(
            name="Other Console Grant Space",
            slug="other-console-grant-space",
            created_by=self.creator,
        )
        self.activity_a = Activity.objects.create(
            space=self.space,
            created_by=self.creator,
            title="Activité A",
            status=ActivityStatus.PUBLISHED,
        )
        self.activity_b = Activity.objects.create(
            space=self.space,
            created_by=self.creator,
            title="Activité B",
            status=ActivityStatus.PUBLISHED,
        )
        self.foreign_activity = Activity.objects.create(
            space=self.other_space,
            created_by=self.creator,
            title="Activité étrangère",
            status=ActivityStatus.PUBLISHED,
        )
        now = timezone.now()
        self.occurrence_a = Occurrence.objects.create(
            activity=self.activity_a,
            start_at=now + timedelta(days=2),
            end_at=now + timedelta(days=2, hours=2),
            status=OccurrenceStatus.SCHEDULED,
        )
        self.occurrence_b = Occurrence.objects.create(
            activity=self.activity_b,
            start_at=now + timedelta(days=3),
            end_at=now + timedelta(days=3, hours=2),
            status=OccurrenceStatus.SCHEDULED,
        )
        self.foreign_occurrence = Occurrence.objects.create(
            activity=self.foreign_activity,
            start_at=now + timedelta(days=4),
            end_at=now + timedelta(days=4, hours=2),
            status=OccurrenceStatus.SCHEDULED,
        )
        grant_space_role(
            profile=self.owner,
            space=self.space,
            role=SystemRoleCode.SPACE_OWNER,
        )
        grant_activity_role(
            profile=self.local_manager,
            activity=self.activity_a,
            role=SystemRoleCode.ACTIVITY_LOCAL_MANAGER,
        )

        view_permission = Permission.objects.get(code=PermissionCode.ACTIVITY_ACCESS_VIEW)
        viewer_role = Role.objects.create(
            code="task18-access-viewer",
            name="Task18 Access viewer",
            scope_type=AuthorityScope.ACTIVITY,
            is_system=True,
            is_active=True,
        )
        RolePermission.objects.create(role=viewer_role, permission=view_permission)
        Mandate.objects.create(
            profile=self.viewer,
            role=viewer_role,
            scope_type=AuthorityScope.ACTIVITY,
            activity=self.activity_a,
        )

        default_team = Team.objects.create(
            organization=self.space,
            name="Équipe test sans mandat",
            is_default=True,
            is_active=True,
        )
        TeamMembership.objects.create(
            team=default_team,
            user=self.team_only,
            joined_at=timezone.now(),
        )

    @property
    def access_url(self):
        return reverse("organizations:console-access", kwargs={"slug": self.space.slug})

    @property
    def grant_url(self):
        return reverse("organizations:console-access-grant", kwargs={"slug": self.space.slug})

    def test_owner_sees_grant_cta_and_can_grant_by_exact_case_insensitive_email(self):
        self.client.force_login(self.owner)
        response = self.client.get(self.access_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Accorder un accès")

        response = self.client.post(
            self.grant_url,
            {
                "beneficiary_email": "Beneficiary.Grant@Example.Com",
                "activity": str(self.activity_a.pk),
                "occurrence": str(self.occurrence_a.pk),
                "reason": "Accès presse",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Accès accordé")
        access = Access.objects.get(beneficiary=self.beneficiary, activity=self.activity_a)
        self.assertEqual(access.issued_by, self.owner)
        self.assertEqual(access.status, AccessStatus.VALID)
        self.assertContains(response, "Accordé par Naomi Kabongo")

    def test_local_manager_form_and_post_are_limited_to_its_activity_scope(self):
        self.client.force_login(self.local_manager)
        response = self.client.get(self.grant_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Activité A")
        self.assertNotContains(response, "Activité B")
        self.assertNotContains(response, "Activité étrangère")

        response = self.client.post(
            self.grant_url,
            {
                "beneficiary_email": self.beneficiary.email,
                "activity": str(self.activity_b.pk),
                "occurrence": str(self.occurrence_b.pk),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.assertFalse(Access.objects.filter(activity=self.activity_b).exists())

    def test_cross_space_forgery_is_rejected(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            self.grant_url,
            {
                "beneficiary_email": self.beneficiary.email,
                "activity": str(self.foreign_activity.pk),
                "occurrence": str(self.foreign_occurrence.pk),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.assertFalse(Access.objects.filter(activity=self.foreign_activity).exists())

    def test_invalid_or_inactive_email_returns_product_error_without_account_creation(self):
        self.client.force_login(self.owner)
        before_users = User.objects.count()
        for email in ("missing.grant@example.com", self.inactive.email):
            with self.subTest(email=email):
                response = self.client.post(
                    self.grant_url,
                    {
                        "beneficiary_email": email,
                        "activity": str(self.activity_a.pk),
                        "occurrence": str(self.occurrence_a.pk),
                    },
                )
                self.assertEqual(response.status_code, 200)
                self.assertContains(
                    response,
                    "Aucun compte Makolo actif ne correspond à cette adresse.",
                )
        self.assertEqual(User.objects.count(), before_users)
        self.assertFalse(Access.objects.exists())

    def test_access_viewer_can_read_but_sees_no_mutation_cta_or_revoke_button(self):
        access = issue_access(
            beneficiary=self.beneficiary,
            activity=self.activity_a,
            occurrence=self.occurrence_a,
            issued_by=self.owner,
        )
        self.client.force_login(self.viewer)
        response = self.client.get(self.access_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.beneficiary.email)
        self.assertNotContains(response, "Accorder un accès")
        self.assertNotContains(response, ">Révoquer<")

        response = self.client.get(self.grant_url)
        self.assertEqual(response.status_code, 403)

        response = self.client.post(
            reverse(
                "organizations:console-access-revoke",
                kwargs={"slug": self.space.slug, "access_id": access.pk},
            )
        )
        self.assertEqual(response.status_code, 302)
        access.refresh_from_db()
        self.assertEqual(access.status, AccessStatus.VALID)

    def test_team_membership_without_mandate_does_not_grant_console_authority(self):
        self.client.force_login(self.team_only)
        self.assertEqual(self.client.get(self.access_url).status_code, 403)
        self.assertEqual(self.client.get(self.grant_url).status_code, 403)
        self.assertFalse(Access.objects.exists())

    def test_get_never_creates_an_access(self):
        self.client.force_login(self.owner)
        response = self.client.get(self.grant_url)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Access.objects.exists())
