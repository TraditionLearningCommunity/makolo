"""MT3: native G1 creation is an Activity owner command, not a parallel model."""
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import User
from activities.models import Activity
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role, grant_space_role, revoke_mandate
from organizations.models import Organization, SpaceArchetype
from subscriptions.runtime_models import Subscription


class SpaceG1NativeActivityCreateTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="mt3-create-owner", password="x",
        )
        self.operator = User.objects.create_user(
            username="mt3-create-operator", password="x",
        )
        self.outsider = User.objects.create_user(
            username="mt3-create-outsider", password="x",
        )
        self.space = Organization.objects.create(
            name="Space G1",
            slug="mt3-create-space",
            created_by=self.owner,
            archetype=SpaceArchetype.COMMUNITY,
        )
        grant_space_role(
            profile=self.owner, space=self.space,
            role=SystemRoleCode.SPACE_OWNER, granted_by=self.owner,
        )
        self.client = APIClient()
        self.url = reverse(
            "organizations_api:workspace-work-activity-create",
            kwargs={"slug": self.space.slug},
        )
        self.client.force_authenticate(self.owner)

    def payload(self, **changes):
        return {
            "title": "Action citoyenne",
            "short_description": "Projet local",
            "description": "Aider nos voisins",
            "visibility": "private",
            **changes,
        }

    def test_canonical_activity_brouillon_belongs_only_to_space(self):
        response = self.client.post(self.url, self.payload(), format="json")
        self.assertEqual(response.status_code, 201, response.data)
        created = Activity.objects.get(pk=response.data["activity"]["id"])
        self.assertEqual(created.space_id, self.space.pk)
        self.assertIsNone(created.owner_profile_id)
        self.assertEqual(created.created_by_id, self.owner.pk)
        self.assertEqual(created.title, "Action citoyenne")
        self.assertEqual(created.status, "draft")
        self.assertEqual(created.visibility, "private")
        self.assertEqual(response.data["space"]["id"], str(self.space.pk))
        self.assertEqual(response.data["space"]["slug"], self.space.slug)
        self.assertEqual(response["Cache-Control"], "private, no-store")

    def test_no_organization_forgery_or_invalid_form(self):
        self.assertEqual(self.client.post(
            self.url, self.payload(organization=str(self.space.pk)),
            format="json",
        ).status_code, 400)
        self.assertEqual(self.client.post(
            self.url, self.payload(title="  "), format="json",
        ).status_code, 400)
        self.assertEqual(self.client.post(
            self.url, self.payload(visibility="public-but-not-validated"),
            format="json",
        ).status_code, 400)
        self.assertFalse(Activity.objects.filter(
            title="Action citoyenne", space=self.space,
        ).exists())

    def test_activity_mandate_does_not_grant_space_creation(self):
        existing = Activity.objects.create(
            title="Initiative existante",
            space=self.space,
            created_by=self.owner,
        )
        mandate = grant_activity_role(
            profile=self.operator, activity=existing,
            role_code=SystemRoleCode.ACTIVITY_MANAGER,
            granted_by=self.owner,
        )
        self.client.force_authenticate(self.operator)
        self.assertEqual(self.client.post(
            self.url, self.payload(), format="json",
        ).status_code, 404)
        self.assertFalse(
            Activity.objects.filter(title="Action citoyenne").exists(),
        )
        revoke_mandate(mandate=mandate, actor=self.owner)
        self.assertEqual(self.client.post(
            self.url, self.payload(), format="json",
        ).status_code, 404)

    def test_outsider_and_other_archetype_cannot_use_g1_creator(self):
        self.client.force_authenticate(self.outsider)
        self.assertEqual(self.client.post(
            self.url, self.payload(), format="json",
        ).status_code, 404)
        self.client.force_authenticate(self.owner)
        self.space.archetype = SpaceArchetype.EDUCATION
        self.space.save(update_fields=["archetype", "updated_at"])
        self.assertEqual(self.client.post(
            self.url, self.payload(), format="json",
        ).status_code, 404)

    def test_subscription_denial_from_canonical_owner_prevents_create(self):
        subscription = Subscription.objects.get(space=self.space)
        subscription.status = "suspended"
        subscription.save(update_fields=["status"])
        root = self.client.get(
            reverse("organizations_api:workspace-work", kwargs={"slug": self.space.slug})
        )
        self.assertEqual(root.status_code, 200)
        self.assertFalse(root.data["capabilities"]["create_activity"])
        response = self.client.post(self.url, self.payload(), format="json")
        self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(Activity.objects.filter(
            title="Action citoyenne", space=self.space,
        ).exists())
