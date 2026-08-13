from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from authorization.constants import PermissionCode, SystemRoleCode
from authorization.services import can
from groups.models import Group, GroupMembership
from organizations.models import TeamMembership, TeamMembershipStatus
from organizations.services import add_or_update_member, create_organization, ensure_default_team

from .models import Place, SpacePlaceRole
from .services import attach_place_to_space, deactivate_space_place


class SpacePlacePermissionTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(email="owner.geo@example.test", username="owner-geo")
        self.admin = User.objects.create_user(email="admin.geo@example.test", username="admin-geo")
        self.finance = User.objects.create_user(email="finance.geo@example.test", username="finance-geo")
        self.team_only = User.objects.create_user(email="team.geo@example.test", username="team-geo")
        self.group_member = User.objects.create_user(email="group.geo@example.test", username="group-geo")
        self.other_owner = User.objects.create_user(email="other.geo@example.test", username="other-geo")
        self.space = create_organization(creator=self.owner, name="Geo Space")
        self.other_space = create_organization(creator=self.other_owner, name="Other Geo Space")
        add_or_update_member(organization=self.space, actor=self.owner, user=self.admin, role=SystemRoleCode.SPACE_ADMIN)
        add_or_update_member(organization=self.space, actor=self.owner, user=self.finance, role=SystemRoleCode.FINANCE)
        team = ensure_default_team(self.space)
        TeamMembership.objects.create(team=team, user=self.team_only, status=TeamMembershipStatus.ACTIVE, invited_by=self.owner)
        group = Group.objects.create(name="Geo Members", space=self.space, created_by=self.owner)
        GroupMembership.objects.create(group=group, profile=self.group_member)
        self.place = Place.objects.create(name="Shared Place", locality="Lubumbashi", country_code="CD")

    def test_owner_and_admin_manage_but_unrelated_authority_does_not(self):
        self.assertTrue(can(self.owner, PermissionCode.SPACE_PLACES_MANAGE, self.space))
        self.assertTrue(can(self.admin, PermissionCode.SPACE_PLACES_MANAGE, self.space))
        self.assertFalse(can(self.finance, PermissionCode.SPACE_PLACES_MANAGE, self.space))
        self.assertFalse(can(self.team_only, PermissionCode.SPACE_PLACES_MANAGE, self.space))
        self.assertFalse(can(self.group_member, PermissionCode.SPACE_PLACES_MANAGE, self.space))
        self.assertFalse(can(self.other_owner, PermissionCode.SPACE_PLACES_MANAGE, self.space))

    def test_place_can_be_reused_by_two_spaces_and_deactivated(self):
        relation = attach_place_to_space(actor=self.owner, organization=self.space, place=self.place, role=SpacePlaceRole.BRANCH, is_primary=True, is_public=True)
        other = attach_place_to_space(actor=self.other_owner, organization=self.other_space, place=self.place, role=SpacePlaceRole.OFFICE)
        self.assertEqual(relation.place_id, other.place_id)
        deactivate_space_place(actor=self.owner, relation=relation)
        relation.refresh_from_db()
        self.assertFalse(relation.is_active)
        self.assertFalse(relation.is_primary)

    def test_other_space_cannot_edit_relation_over_web(self):
        relation = attach_place_to_space(actor=self.owner, organization=self.space, place=self.place, role=SpacePlaceRole.OFFICE)
        self.client.force_login(self.other_owner)
        response = self.client.get(reverse("organizations:place-relation-edit", kwargs={"slug": self.space.slug, "pk": relation.pk}))
        self.assertEqual(response.status_code, 403)
