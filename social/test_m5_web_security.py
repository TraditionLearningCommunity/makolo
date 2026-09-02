from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from groups.models import Group, GroupMembership, GroupMembershipStatus
from organizations.models import Organization

from .models import ContributionKind
from .services import create_contribution

User = get_user_model()


class M5WebSecurityTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="m5-web-owner", password="StrongPass2026!")
        self.member = User.objects.create_user(username="m5-web-member", password="StrongPass2026!")
        self.outsider = User.objects.create_user(username="m5-web-outsider", password="StrongPass2026!")
        self.space = Organization.objects.create(name="M5 Web Space", created_by=self.owner, public_profile=True)
        self.group = Group.objects.create(name="M5 Web Private Group", owner_profile=self.owner, created_by=self.owner)
        GroupMembership.objects.create(group=self.group, profile=self.member, status=GroupMembershipStatus.ACTIVE)
        self.contribution = create_contribution(actor=self.member, kind=ContributionKind.DISCUSSION, body="Contexte privé", group=self.group)

    def test_network_requires_authentication(self):
        response = self.client.get(reverse("social:network"))
        self.assertEqual(response.status_code, 302)

    def test_private_group_page_rejects_outsider(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse("social:group", kwargs={"slug": self.group.slug}))
        self.assertEqual(response.status_code, 403)
        self.assertNotContains(response, "Contexte privé", status_code=403)

    def test_outsider_cannot_reply_to_private_group_contribution(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse("social:reply", kwargs={"pk": self.contribution.pk}), {"body": "Intrusion"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.contribution.replies.count(), 0)

    def test_owner_cannot_change_another_profiles_goal_through_web(self):
        from datetime import date, timedelta
        from goals.services import create_personal_goal
        goal = create_personal_goal(profile=self.member, goal_type="journeys_completed", target_value=1, period_start=date.today(), period_end=date.today() + timedelta(days=30))
        self.client.force_login(self.outsider)
        response = self.client.post(reverse("goals:status", kwargs={"pk": goal.pk}), {"status": "paused"})
        self.assertEqual(response.status_code, 403)
        goal.refresh_from_db()
        self.assertEqual(goal.status, "active")
