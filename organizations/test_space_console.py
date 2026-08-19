from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from access.models import AccessStatus, AccessUseResult
from access.services import issue_access, render_access_credential
from activities.models import Activity, Occurrence
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role, grant_space_role
from events.models import Event
from groups.models import Group, GroupMembership
from organizations.console_context import SpaceConsoleContext, authorized_spaces
from organizations.models import Organization, Team, TeamMembership


User = get_user_model()


class SpaceConsoleAuthorityTests(TestCase):
    def setUp(self):
        self.creator = User.objects.create_user(username="console-creator", email="creator@example.com", password="Console-2026!")
        self.owner = User.objects.create_user(username="console-owner", email="owner@example.com", password="Console-2026!")
        self.finance = User.objects.create_user(username="console-finance", email="finance@example.com", password="Console-2026!")
        self.marketing = User.objects.create_user(username="console-marketing", email="marketing@example.com", password="Console-2026!")
        self.activity_manager = User.objects.create_user(username="console-activity", email="activity@example.com", password="Console-2026!")
        self.local_manager = User.objects.create_user(username="console-local", email="local@example.com", password="Console-2026!")
        self.scanner = User.objects.create_user(username="console-scanner", email="scanner@example.com", password="Console-2026!")
        self.participant = User.objects.create_user(username="console-participant", email="participant@example.com", password="Console-2026!")
        self.team_only = User.objects.create_user(username="console-team-only", email="team-only@example.com", password="Console-2026!")
        self.group_only = User.objects.create_user(username="console-group-only", email="group-only@example.com", password="Console-2026!")

        self.space_a = Organization.objects.create(name="Mulykap", created_by=self.creator)
        self.space_b = Organization.objects.create(name="CAA", created_by=self.creator)
        self.team = Team.objects.create(organization=self.space_a, name="Équipe principale", is_default=True)
        TeamMembership.objects.create(team=self.team, user=self.team_only)
        group = Group.objects.create(name="Bénévoles", space=self.space_a, created_by=self.creator)
        GroupMembership.objects.create(group=group, profile=self.group_only)

        self.activity_a = Activity.objects.create(space=self.space_a, created_by=self.creator, title="Atelier canonique")
        self.activity_b = Activity.objects.create(space=self.space_a, created_by=self.creator, title="Deuxième activité")
        self.other_activity = Activity.objects.create(space=self.space_b, created_by=self.creator, title="Activité CAA")
        now = timezone.now()
        self.occurrence = Occurrence.objects.create(
            activity=self.activity_a,
            start_at=now - timedelta(minutes=5),
            end_at=now + timedelta(hours=2),
            timezone="Africa/Kinshasa",
        )

        grant_space_role(profile=self.owner, space=self.space_a, role=SystemRoleCode.SPACE_OWNER)
        grant_space_role(profile=self.finance, space=self.space_a, role=SystemRoleCode.FINANCE)
        grant_space_role(profile=self.marketing, space=self.space_a, role=SystemRoleCode.MARKETING)
        grant_space_role(profile=self.activity_manager, space=self.space_a, role=SystemRoleCode.ACTIVITY_MANAGER)
        grant_activity_role(profile=self.local_manager, activity=self.activity_a, role=SystemRoleCode.ACTIVITY_LOCAL_MANAGER)
        grant_activity_role(profile=self.scanner, activity=self.activity_a, role=SystemRoleCode.ACTIVITY_SCANNER)

    def _navigation_keys(self, user):
        context = SpaceConsoleContext.build(user, self.space_a)
        self.assertIsNotNone(context)
        return {item["key"] for group in context.navigation_groups for item in group["items"]}

    def test_owner_gets_full_space_console(self):
        keys = self._navigation_keys(self.owner)
        for expected in {"activities", "requests", "access", "offers", "orders", "payments", "groups", "crm", "audiences", "promotions", "places", "control", "operations", "analytics", "automation", "team", "settings"}:
            self.assertIn(expected, keys)

    def test_finance_isolated_from_activity_crm_and_scanner(self):
        keys = self._navigation_keys(self.finance)
        self.assertTrue({"orders", "payments", "analytics"}.issubset(keys))
        self.assertFalse({"activities", "requests", "crm", "audiences", "control", "team", "settings"} & keys)

        self.client.force_login(self.finance)
        response = self.client.get(reverse("organizations:console-overview", kwargs={"slug": self.space_a.slug}))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Demandes</p>")
        self.assertNotContains(response, "Contrôle d’accès")
        self.assertEqual(self.client.get(reverse("organizations:console-crm", kwargs={"slug": self.space_a.slug})).status_code, 403)
        self.assertEqual(self.client.get(reverse("organizations:console-activities", kwargs={"slug": self.space_a.slug})).status_code, 403)

    def test_marketing_sees_publics_but_not_finance_or_access(self):
        keys = self._navigation_keys(self.marketing)
        self.assertTrue({"crm", "audiences", "promotions", "analytics"}.issubset(keys))
        self.assertFalse({"payments", "orders", "access", "control", "activities"} & keys)

    def test_space_activity_manager_uses_canonical_activity_modules(self):
        keys = self._navigation_keys(self.activity_manager)
        self.assertTrue({"activities", "requests", "access", "offers", "orders", "operations", "analytics"}.issubset(keys))
        self.assertNotIn("payments", keys)
        self.assertNotIn("crm", keys)

    def test_activity_local_mandate_sees_only_its_activity(self):
        spaces = list(authorized_spaces(self.local_manager))
        self.assertEqual(spaces, [self.space_a])
        context = SpaceConsoleContext.build(self.local_manager, self.space_a)
        self.assertTrue(context.limited_to_activities)
        self.assertEqual(context.activity_ids, frozenset({self.activity_a.pk}))

        self.client.force_login(self.local_manager)
        allowed = reverse("organizations:console-activity-detail", kwargs={"slug": self.space_a.slug, "activity_id": self.activity_a.pk})
        denied = reverse("organizations:console-activity-detail", kwargs={"slug": self.space_a.slug, "activity_id": self.activity_b.pk})
        self.assertEqual(self.client.get(allowed).status_code, 200)
        self.assertEqual(self.client.get(denied).status_code, 403)
        self.assertEqual(self.client.get(reverse("organizations:console-team", kwargs={"slug": self.space_a.slug})).status_code, 403)
        self.assertEqual(self.client.get(reverse("organizations:console-settings", kwargs={"slug": self.space_a.slug})).status_code, 403)

    def test_non_event_activity_is_visible_and_openable(self):
        self.assertFalse(Event.objects.filter(activity=self.activity_a).exists())
        self.client.force_login(self.owner)
        listing = self.client.get(reverse("organizations:console-activities", kwargs={"slug": self.space_a.slug}))
        self.assertContains(listing, "Atelier canonique")
        detail = self.client.get(reverse("organizations:console-activity-detail", kwargs={"slug": self.space_a.slug, "activity_id": self.activity_a.pk}))
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, "Occurrences")

    def test_team_membership_without_mandate_grants_no_console_authority(self):
        self.assertFalse(authorized_spaces(self.team_only).exists())
        self.client.force_login(self.team_only)
        response = self.client.get(reverse("organizations:console-overview", kwargs={"slug": self.space_a.slug}))
        self.assertEqual(response.status_code, 403)

    def test_group_membership_without_mandate_grants_no_console_authority(self):
        self.assertFalse(authorized_spaces(self.group_only).exists())
        self.client.force_login(self.group_only)
        response = self.client.get(reverse("organizations:console-overview", kwargs={"slug": self.space_a.slug}))
        self.assertEqual(response.status_code, 403)

    def test_cross_space_direct_object_access_is_denied(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(reverse("organizations:console-overview", kwargs={"slug": self.space_b.slug})).status_code, 403)
        self.assertEqual(
            self.client.get(reverse("organizations:console-activity-detail", kwargs={"slug": self.space_b.slug, "activity_id": self.other_activity.pk})).status_code,
            403,
        )

    def test_participant_only_has_no_professional_space(self):
        self.assertFalse(authorized_spaces(self.participant).exists())
        self.client.force_login(self.participant)
        listing = self.client.get(reverse("organizations:list"))
        self.assertEqual(listing.status_code, 200)
        self.assertNotContains(listing, "Mulykap")
        self.assertEqual(self.client.get(reverse("organizations:console-entry", kwargs={"slug": self.space_a.slug})).status_code, 403)

    def test_scanner_mandate_uses_canonical_access_and_duplicate_refusal(self):
        access = issue_access(
            beneficiary=self.participant,
            activity=self.activity_a,
            occurrence=self.occurrence,
            issued_by=self.owner,
        )
        credential = access.credentials.get()
        token = render_access_credential(credential)

        self.client.force_login(self.scanner)
        url = reverse("organizations:console-control-activity", kwargs={"slug": self.space_a.slug, "activity_id": self.activity_a.pk})
        first = self.client.post(url, {"token": token, "occurrence": str(self.occurrence.pk)})
        self.assertEqual(first.status_code, 200)
        access.refresh_from_db()
        self.assertEqual(access.status, AccessStatus.USED)
        self.assertEqual(access.uses.order_by("used_at").first().result, AccessUseResult.ACCEPTED)

        second = self.client.post(url, {"token": token, "occurrence": str(self.occurrence.pk)})
        self.assertEqual(second.status_code, 200)
        self.assertFalse(second.context["scan_outcome"].accepted)
        self.assertEqual(access.uses.count(), 2)
