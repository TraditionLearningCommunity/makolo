from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from activities.models import Activity
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role, grant_space_role
from automation.models import AutomationRule
from domain_events.contracts import DomainEventType

from .console_context import SpaceConsoleContext
from .console_selectors import automation_rules_for_console, overview_for_console
from .models import Organization


User = get_user_model()


class M8DSpaceNowTests(TestCase):
    def setUp(self):
        self.creator = User.objects.create_user(username="m8d-creator", email="m8d-creator@example.com")
        self.owner = User.objects.create_user(username="m8d-owner", email="m8d-owner@example.com")
        self.local_manager = User.objects.create_user(username="m8d-local", email="m8d-local@example.com")
        self.space = Organization.objects.create(name="M8-D Espace", created_by=self.creator)
        self.activity = Activity.objects.create(space=self.space, created_by=self.creator, title="Activité autorisée")
        self.other_activity = Activity.objects.create(space=self.space, created_by=self.creator, title="Activité hors portée")
        grant_space_role(profile=self.owner, space=self.space, role=SystemRoleCode.SPACE_OWNER)
        grant_activity_role(
            profile=self.local_manager,
            activity=self.activity,
            role=SystemRoleCode.ACTIVITY_LOCAL_MANAGER,
        )

    def _rule(self, *, name, activity=None):
        return AutomationRule.objects.create(
            space=self.space,
            activity=activity,
            name=name,
            trigger_event_type=DomainEventType.JOURNEY_SUBMITTED,
            conditions={},
            action_config={
                "recipient": "beneficiary",
                "title": "Action requise",
                "message": "Une situation demande votre attention.",
                "category": "system",
            },
            created_by=self.creator,
        )

    def test_activity_limited_context_excludes_space_level_automation_rules(self):
        allowed = self._rule(name="Activité autorisée", activity=self.activity)
        self._rule(name="Espace entier")
        self._rule(name="Autre activité", activity=self.other_activity)

        limited_context = SpaceConsoleContext.build(self.local_manager, self.space)
        self.assertTrue(limited_context.limited_to_activities)
        self.assertEqual(
            list(automation_rules_for_console(limited_context).values_list("id", flat=True)),
            [allowed.id],
        )

        owner_context = SpaceConsoleContext.build(self.owner, self.space)
        self.assertEqual(automation_rules_for_console(owner_context).count(), 3)

    def test_space_now_can_be_calm_without_decorative_metrics(self):
        context = SpaceConsoleContext.build(self.owner, self.space)
        presentation = overview_for_console(context)
        self.assertTrue(presentation["all_clear"])
        self.assertFalse(any(presentation["action_items"].values()))

        self.client.force_login(self.owner)
        response = self.client.get(reverse("organizations:console-overview", kwargs={"slug": self.space.slug}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Tout est en ordre. ✓")
        self.assertContains(response, "Ce qui compte maintenant")
        self.assertNotContains(response, "Aperçu activité")
